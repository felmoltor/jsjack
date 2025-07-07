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
            discord_webhook: str=None,
            scrapeops_key: str=None,
            max_pages: int=None,
            max_items: int=None,
            max_depth: int=None,
            dns: str=None,
            scan_images: bool=False,
            logging_level: str=None,
            **kwargs
        ):
        super().__init__(self.name, **kwargs)

        # Read the project settings as fallback values
        settings = get_project_settings()
        
        # Initialize instance attributes with arguments or fallback to settings
        self.discord_webhook = discord_webhook or settings.get('DISCORD_WEBHOOK')
        self.scrapeops_key = scrapeops_key or settings.get('SCRAPEOPS_KEY')
        self.max_pages_per_fld = int(max_pages) if max_pages else settings.getint('MAX_PAGES_PER_FLD', 100)
        self.max_items_per_fld = int(max_items) if max_items else settings.getint('MAX_ITEMS_PER_FLD', 100)
        self.depth_limit = int(max_depth) if max_depth else settings.getint('DEPTH_LIMIT', 2)
        self.dns_server = dns or settings.get('DNS_SERVER', '8.8.8.8')
        self.scan_images = scan_images or settings.get('SCAN_IMAGES', False)
        self.logging_level = logging_level or settings.get('LOG_LEVEL', 'INFO')

        # Initialize counters
        self.pages_counter = Counter()
        self.items_counter = Counter()

        # Initialize domain lists
        self._populate_fdl()

        # Configure proxy usage
        self.use_proxies = bool(settings.get("PROXIES"))

        # Configure scrapeops
        self.use_scrapeops = bool(self.scrapeops_key)

        # Initialize Discord bot
        self.discord = TakeoverDiscordBot(
            webhook_url=self.discord_webhook,
            use_proxies=self.use_proxies,
            settings=settings  # Pass full settings since Discord bot may need other settings
        )

        # Initialize hijacker with direct settings
        self.hijacker = DomainHijacker(
            dns_server=self.dns_server,
            dns_timeout=settings.get('DNS_TIMEOUT', 5),  # Fallback to settings for optional params
            headers=settings.get('HEADERS', {}),
            discord=self.discord,
            logger=self.logger
        )

        # Initialize page counter
        self.scrapped_pages = 0

        # Initialize URLs
        self.start_urls = []
        if not path.exists(urls):
            raise FileNotFoundError(f"The urls file '{urls}' does not exist. Please provide a valid file with URLs to explore.")
        
        logger.info("Using urls file %s" % urls)
        self.urls_file = urls
        with open(self.urls_file, "r") as f:
            self.start_urls = [url.strip() for url in f.readlines() if url.strip()]
        
        # Configure domain settings
        self.allow_fld = bool(allow_fld)
        self.allowed_domains = []
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
            try:
                urlp=urlparse(url)
                self.allowed_domains.append(urlp.netloc)

                # Add also the first level domain if allow_fld is True
                if (self.allow_fld):
                    fld=get_fld(url)
                    self.allowed_domains.append(fld)
            except Exception as e:
                self.logger.error(f"Error parsing URL '{url}': {e}")
                continue
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
        payload = {'api_key': self.scrapeops_key, 'url': url} # , 'bypass': 'cloudflare'}
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

    def _get_remote_source_items(self, response: Response) -> list[JsLink]:
        """
        List all the JavaScript files, iframes and frames in the response and yield JsLink items for each of them.
        :param response: The Scrapy response object.
        :return: A generator of JsLink items for each JavaScript file, iframe and frame found in the response.
        """
        def _populate_items_from_xpath(xpath_results, link_type: LinkType, attrib_name: str) -> list[JsLink]:
            """Populate items from the given XPath results."""
            items=[]
            for xpath_item in xpath_results:
                if not hosted_localy(response.url, xpath_item):
                    # Check for an orphan domain hijack
                    item = self.hijacker.detect_unregistered_domain_hijack(
                        response,
                        self.safe_fld,
                        self.hijackable_fld,
                        source_link=xpath_item,
                        link_type=link_type
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
                items+=self.hijacker.detect_cnames_hijack(response.url, xpath_item.attrib[attrib_name], link_type)
            return items
        
        def hosted_localy(response_url, link):
            """Check if the domain of the remote script is the same of this url"""
            js_fld=get_fld(link.attrib["src"].strip())
            resp_fld=get_fld(response_url)
            return js_fld==resp_fld

        remote_scripts=response.xpath("//script[@src]")
        remote_iframes=response.xpath("//iframe[@src]")
        remote_frames=response.xpath("//frame[@src]")
        items=[]

        items+=_populate_items_from_xpath(remote_scripts, LinkType.JAVASCRIPT, attrib_name="src")
        items+=_populate_items_from_xpath(remote_iframes, LinkType.IFRAME, attrib_name="src")
        items+=_populate_items_from_xpath(remote_frames, LinkType.FRAME, attrib_name="src")
        
        if self.scan_images:
            remote_style_link=response.xpath("//link[@src]")
            remote_images=response.xpath("//img[@src]")
            remote_svg=response.xpath("//svg//a[@href]")
            items+=_populate_items_from_xpath(remote_style_link, LinkType.STYLE, attrib_name="src")
            items+=_populate_items_from_xpath(remote_images, LinkType.IMAGE, attrib_name="src")
            items+=_populate_items_from_xpath(remote_svg, LinkType.SVG, attrib_name="href")

        return items
    
    def _exceded_crawling(self, fld: str):
        if (self.pages_counter.get(fld)):
            return self.pages_counter.get(fld) > self.max_pages_per_fld
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
                        requests_send.append(Request(url=so_url, callback=self.parse))
                    else:
                        requests_send.append(Request(url=target, callback=self.parse))
                else:
                    self.logger.info(f"[TakeoverSpider] In URL {response.url}. Ignoring the link to {target} ({target_fld}), as we reached the page limit ({self.pages_counter.get(target_fld)} > {self.max_pages_per_fld})")
        
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
        items = self._get_remote_source_items(response)
        
        if items:
            self.logger.debug(f"Found {len(items)} remote source items in the response.")
            # Yield the items that were created from the JavaScript files, iframes and frames
            for item in items:
                if item is not None:
                    self.logger.debug(f"Yielding {item['type']} item: {item}")
                    yield item




