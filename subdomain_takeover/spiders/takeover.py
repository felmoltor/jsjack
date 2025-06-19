from scrapy import signals
from ..items import JsLink, LinkType
from scrapy.spiders import Spider, Request, Response 
from scrapy.utils.project import get_project_settings
from urllib.parse import urlparse, urljoin, urlencode
import logging
from tldextract import extract as tld_extract
from os import path
from collections import Counter
from subdomain_takeover.spiders.utils.discord import TakeoverDiscordBot
from subdomain_takeover.spiders.utils.hijacker import DomainHijacker

logger = logging.getLogger('takeover-spider')

def get_fld(url):
    ext=tld_extract(url)
    return f"{ext.domain}.{ext.suffix}"

class TakeoverSpider(Spider):
    name = 'takeover'
    safe_fdl_file = 'output/safe_domains.txt'
    hijackable_fdl_file = 'output/hijackable_domains.txt'

    def __init__(
            self,
            urls: str,
            allow_fld: str=None,
            # discord_webhook: str=None,
            # scrapeops_key: str=None,
            # max_pages: int=None,
            # max_items: int=None,
            # max_depth: int=None,
            # dns: str=None,
            # logging_level: str=None,
            **kwargs
        ):
        super().__init__(self.name, **kwargs)

        # Read the project settings
        self.settings=get_project_settings()

        self.logger.info('============================')
        self.logger.info(f"MAX_PAGES_PER_FLD: {self.settings.get('MAX_PAGES_PER_FLD')}")
        self.logger.info(f"MAX_ITEMS_PER_FLD: {self.settings.get('MAX_ITEMS_PER_FLD')}")
        self.logger.info(f"DEPTH_LIMIT: {self.settings.get('DEPTH_LIMIT')}")
        self.logger.info(f"DNS_SERVER: {self.settings.get('DNS_SERVER')}")
        self.logger.info('============================')

        # Overwrite settings if they are defined via arguments
        # if discord_webhook:
        #     self.settings.set('DISCORD_WEBHOOK', discord_webhook)
        # if scrapeops_key:
        #     self.settings.set('SCRAPEOPS_KEY', scrapeops_key)
        # if max_pages:
        #     self.logger.debug(f"Setting MAX_PAGES_PER_FLD to {max_pages}")
        #     self.settings.set('MAX_PAGES_PER_FLD', max_pages)
        # if max_items:
        #     self.logger.debug(f"Setting MAX_ITEMS_PER_FLD to {max_items}")
        #     self.settings.set('MAX_ITEMS_PER_FLD', max_items)
        # if max_depth:
        #     self.logger.debug(f"Setting DEPTH_LIMIT to {max_depth}")
        #     self.settings.set('DEPTH_LIMIT', max_depth)
        # if dns:
        #     self.settings.set('DNS_SERVER', dns)
        # # Fix this, setting the log level like this does not work and always shows DEBUG
        # if logging_level:
        #     self.settings.set('LOG_LEVEL', logging_level)

        # Initialize the max pages and items dictionary
        self.pages_counter = Counter()
        self.items_counter = Counter()

        # Initialize the list of safe and hijackable fdl domains
        self._populate_fdl()

        # If proxies are defined in settings, use them
        self.use_proxies=self.settings.get("PROXIES", None) != None

        # If scrapeops token is defined in settings, use it
        self.scrapeops_api_key=self.settings.get("SCRAPEOPS_KEY", None)
        self.use_scrapeops=self.scrapeops_api_key != None

        # Initialize de Discord bot to notify about takeovers
        self.discord = TakeoverDiscordBot(
            webhook_url=self.settings.get("DISCORD_WEBHOOK"), 
            use_proxies=self.use_proxies, 
            settings=self.settings
        )

        # Initialize the hijacker class to detect hijackable domains
        self.hijacker = DomainHijacker(settings=self.settings, discord=self.discord, logger=self.logger)

        # Initialize the counter of scrapped pages
        self.scrapped_pages=0

        # If there is a urls file, read it and store it in start_urls
        self.urls_file = urls
        self.start_urls = []
        if (not path.exists(self.urls_file)):
            raise FileNotFoundError(f"The urls file '{self.urls_file}' does not exist. Please provide a valid file with URLs to explore.")
        else:
            logger.info("Using urls file %s" % self.urls_file)
            # Read start urls from file
            with open(self.urls_file, "r") as f:
                self.start_urls = [url.strip() for url in f.readlines() if url.strip()]
        
        # Populate the allowed domains set
        self.allow_fld=bool(allow_fld)
        self.allowed_domains=[]
        self._populate_allowed_domains()

    def _populate_fdl(self):
        self.safe_fld = set()
        self.hijackable_fld = set()
        # Read the safe and hijackable fdl from the files safe_domains.txt and hijackable_domains.txt
        if path.exists(self.safe_fdl_file):
            with open(self.safe_fdl_file, "r") as f:
                self.safe_fld = set([line.strip() for line in f.readlines() if line.strip()])
                self.logger.debug("Loaded %d safe first level domains from file." % len(self.safe_fld))
        else:
            self.logger.warning("Safe first level domains file '%s' does not exist. No safe fdl domains loaded. Creating file." % self.safe_fdl_file)
            # Create the file if it does not exist
            with open(self.safe_fdl_file, "w") as f:
                f.write("")

        if path.exists(self.hijackable_fdl_file):
            with open(self.hijackable_fdl_file, "r") as f:
                self.hijackable_fld = set([line.strip() for line in f.readlines() if line.strip()])
                self.logger.debug("Loaded %d hijackable first level domains from file." % len(self.hijackable_fld))
        else:
            self.logger.warning("Hijackable first level domains file '%s' does not exist. No hijackable fdl domains loaded. Creating file" % self.hijackable_fdl_file)
            # Create the file if it does not exist
            with open(self.hijackable_fdl_file, "w") as f:
                f.write("")


    def _populate_allowed_domains(self):
        """
        Populate the allowed domains set from the settings.
        :return: A set of allowed domains.
        """
        # Decide whether to allow first domain level allowlist
        for url in self.start_urls:
            # Add the base domain to the allowed domains set
            self.allowed_domains.append(urlparse(url).netloc)

            # Add also the first level domain if allow_fld is True
            if (self.allow_fld):
                fld=get_fld(url)
                self.allowed_domains.append(fld)
        # Manually add also the scrapeops proxy domain if it is used
        if (self.use_scrapeops):
            self.allowed_domains.append("proxy.scrapeops.io")

    def _row_to_item(self, row):
        """
        Convert a database row to a JsLink item.
        :param row: A tuple containing the database row data.
        :return: A JsLink item
        """
        item = JsLink()
        item['hijackable_domain'] = row[0]
        item['script_domain_fld'] = row[1]
        item['parent_domain'] = row[2]
        item['parent_url'] = row[3]
        item['embedded_url'] = row[4]
        item['hijackable'] = row[5] == 1
        item['cname_hijackable'] = row[6] == 1
        item['type'] = LinkType(row[7])
        return item

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """
        Class method to use signals and create the spider instance.
        :param crawler: The Scrapy crawler object.
        :param args: Additional arguments.
        :param kwargs: Additional keyword arguments.
        :return: An instance of the TakeoverSpider.
        """
        spider = super(TakeoverSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_opened(self, spider):
        """
        Called when the spider is opened. Will notify Discord about the spider start.
        This method is connected to the Scrapy signal `spider_opened`.
        :param spider: The Scrapy spider object.
        """
        spider.logger.info("Spider opened. Notifying discord")
        self.discord.notify_status(
            "Spider starting",
            self.urls_file,
            len(self.safe_fld),
            len(self.hijackable_fld),
            self.scrapped_pages
        )

    def spider_closed(self, spider):
        """
        Called when the spider is closed. Will notify Discord about the spider close.
        This method is connected to the Scrapy signal `spider_closed`.
        :param spider: The Scrapy spider object.
        """
        spider.logger.info("Spider closed. Notifying discord")
        self.discord.notify_status(
            "Spider finished",
            self.urls_file,
            len(self.safe_fld),
            len(self.hijackable_fld),
            self.scrapped_pages
        )

    def get_scrapeops_url(self,url):
        payload = {'api_key': self.scrapeops_api_key, 'url': url} # , 'bypass': 'cloudflare'}
        proxy_url = 'https://proxy.scrapeops.io/v1/?' + urlencode(payload)
        return proxy_url

    def valid_url(self,url):
        """Check if the URL is valid and has a valid scheme (http or https)"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and all([result.scheme in ['http', 'https']])
        except ValueError:
            return False

    def already_explored(self, domain):
        return domain in self.hijackable_fld or domain in self.safe_fld
    
    # Add a class method to print in the screen the current registered and orphan domains
    # It should be called when the key enter is pressed
    def print_current_domains(self):
        """
        Print the current registered and orphan domains in the screen.
        """
        logger.info("Current registered domains: %s" % (self.registered_domains))
        logger.info("Current orphan domains: %s" % (self.orphan_domains))

    def _get_javascript_items(self, response: Response) -> list[JsLink]:
        """
        List all the JavaScript files, iframes and frames in the response and yield JsLink items for each of them.
        :param response: The Scrapy response object.
        :return: A generator of JsLink items for each JavaScript file, iframe and frame found in the response.
        """
        def hosted_localy(response_url, link):
            # Check if the domain of the remote script is the same of this url
            js_fld=get_fld(link.attrib["src"].strip())
            resp_fld=get_fld(response_url)
            return js_fld==resp_fld

        remote_scripts=response.xpath("//script[@src]")
        remote_iframes=response.xpath("//iframe[@src]")
        remote_frames=response.xpath("//frame[@src]")
        items=[]

        for jslink in remote_scripts:
            if not hosted_localy(response.url, jslink):
                # Check for an orphan domain hijack
                item = self.hijacker.detect_unregistered_domain_hijack(
                    response,
                    self.safe_fld,
                    self.hijackable_fld,
                    source_link=jslink,
                    link_type=LinkType.JAVASCRIPT
                )
                if item:
                    # self.logger.debug(f"Detected item in link {jslink}: {item}")
                    items.append(item)
                    if item['hijackable']:
                        # Add it to the orphan domains set
                        self.hijackable_fld.add(item['script_domain_fld'])
                    else:
                        # Add it to the safe domains set
                        self.safe_fld.add(item['script_domain_fld'])
            # Check for CNAMEs hijack in any of the links
            items+=self.hijacker.detect_cnames_hijack(response.url, jslink.attrib["src"],LinkType.JAVASCRIPT)

        for iframe_link in remote_iframes:
            if not hosted_localy(response.url, iframe_link):
                # Check for an orphan domain hijack
                item = self.hijacker.detect_unregistered_domain_hijack(
                    response,
                    self.safe_fld,
                    self.hijackable_fld,
                    source_link=iframe_link,
                    link_type=LinkType.IFRAME
                )
                if item:
                    items.append(item)
                    if item['hijackable']:
                        # Add it to the orphan domains set
                        self.hijackable_fld.add(item['script_domain_fld'])
                    else:
                        # Add it to the safe domains set
                        self.safe_fld.add(item['script_domain_fld'])
            # Check for CNAMEs hijack in any of the links
            items+=self.hijacker.detect_cnames_hijack(response.url, iframe_link.attrib["src"], LinkType.IFRAME)
        
        for frame_link in remote_frames:
            if not hosted_localy(response.url, frame_link):
                # Check for an orphan domain hijack
                item = self.hijacker.detect_unregistered_domain_hijack(
                    response,
                    self.safe_fld,
                    self.hijackable_fld,
                    source_link=iframe_link,
                    link_type=LinkType.FRAME
                )
                if item:
                    items.append(item)
                    if item['hijackable']:
                        # Add it to the orphan domains set
                        self.hijackable_fld.add(item['script_domain_fld'])
                    else:
                        # Add it to the safe domains set
                        self.safe_fld.add(item['script_domain_fld'])
            # Check for CNAMEs hijack in any of the links
            items+=self.hijacker.detect_cnames_hijack(response.url, frame_link.attrib["src"], LinkType.FRAME)

        return items

    def _exceded_crawling(self, fld: str):
        if (self.pages_counter.get(fld)):
            return self.pages_counter.get(fld) > self.settings.get('MAX_PAGES_PER_FLD')
        else:
            return False

    def _get_links_in_response(self, response: Response) -> list[Request]:
        """
        Extract all the links in the response and yield Scrapy Request objects for each of them.
        :param response: The Scrapy response object.
        :return: A list of Scrapy Request objects for each link found in the response.
        """
        links=response.xpath("//a[@href]")
        requests_send = list()
        
        for link in links:
            href=link.attrib["href"]
            target=urljoin(response.url,href)
            targetp=urlparse(target)
            target_fld = get_fld(target)
            
            # Yield a new Request if the link is not a fragment, is a valid URL, and is not a link to a file
            if (not href.startswith("#") and self.valid_url(href)):
                # logger.debug("Yielding a new Request to %s" % target)
                if (not self._exceded_crawling(target_fld)):
                    if (self.use_scrapeops):
                        so_url=self.get_scrapeops_url(url=target)
                        self.logger.debug("Using scrapeos url %s for the target %s" % (so_url,target))
                        requests_send.append(Request(url=so_url, headers=self.settings.get('HEADERS'), callback=self.parse))
                    else:
                        requests_send.append(Request(url=target, headers=self.settings.get('HEADERS'), callback=self.parse))
                else:
                    self.logger.info(f"[TakeoverSpider] In URL {response.url}. Ignoring the link to {target} ({target_fld}), as we reached the page limit ({self.pages_counter.get(target_fld)} > {self.settings.get('MAX_PAGES_PER_FLD')})")
        
        return requests_send
    
    def _check_parent_domain_cname_hijack(self, response: Response):
        """
        Check if the parent domain of the response has a CNAME hijack.
        :param response: The Scrapy response object.
        """
        response_fld=get_fld(response.url)
        if (not self.already_explored(response_fld)):
            self.hijacker.detect_cnames_hijack(response_fld, response_fld, LinkType.DIRECT)

    def parse(self, response: Response):
        """
        Parse the response and extract links to follow.
        :param response: The Scrapy response object.
        :return: A generator of Scrapy Request objects to follow the links that are not JavaScript files.
        """
        response_fld=get_fld(response.url)

        self.scrapped_pages+=1

        # Check if this current domain has a CNAME hijack
        self._check_parent_domain_cname_hijack(response)
            
        # Yield normal links to parse and crawl down
        requests_send = self._get_links_in_response(response)

        if requests_send:
            # Yield the requests to follow the links
            for request in requests_send:
                yield request

        # Now, check for JavaScript files for each of which will be created a new JsLink item to yield
        items = self._get_javascript_items(response)
        
        if items:
            self.logger.debug(f"Found {len(items)} JavaScript items in the response.")
            # Yield the items that were created from the JavaScript files, iframes and frames
            for item in items:
                if item is not None:
                    yield item
        

        

