import logging
import requests
from tldextract import extract as tld_extract
from subdomain_takeover.items import JsLink, LinkType
from urllib.parse import urlparse
from scrapy.spiders import Response
from dnslib import DNSRecord, RCODE, QTYPE
from subdomain_takeover.spiders.utils.discord import TakeoverDiscordBot
from subdomain_takeover.spiders.utils.whois import WhoisRDAP, WhoisClassic

def get_fld(url):
    ext=tld_extract(url)
    return f"{ext.domain}.{ext.suffix}"

class DomainHijacker:
    """
    A class to check if a domain can be hijacked
    """
    def __init__(
            self, 
            settings=None,  # Keep for backwards compatibility
            dns_server: str = None,
            dns_timeout: int = None,
            headers: dict = None,
            discord: TakeoverDiscordBot=None,
            logger: logging.Logger=None,
            explored_domains: set=None
        ):
        # Get settings from the provided settings or use defaults
        self.dns_server = dns_server or settings.get("DNS_SERVER", "8.8.8.8")
        self.dns_timeout = dns_timeout or settings.get("DNS_TIMEOUT", 5)
        self.headers = headers or settings.get("HEADERS", {})

        self.discord = discord
        self.logger = logger or logging.getLogger('domain-hijacker')
        self.whois_rdap = WhoisRDAP()
        self.whois_classic = WhoisClassic()

    def detect_cnames_hijack(
            self, 
            parent_response_url,
            link_url,
            link_type: LinkType = LinkType.UNKNOWN
        ) -> list[JsLink]:
        """
        Detect if the link_url is a CNAME hijackable domain.
        The logic is inspired by https://github.com/EdOverflow/can-i-take-over-xyz
        :param parent_response_url: The URL of the parent response.
        :param link_url: The URL of the link to check.
        :param link_type: The type of the link (e.g. LinkType.JAVASCRIPT, LinkType.IFRAME, etc.)
        :return: A JsLink item with the hijackable domain information if a CNAME hijack is detected, None otherwise.
        """
        jsitem=None
        parent_domain_name=urlparse(parent_response_url).netloc
        link_domain_name=urlparse(link_url).netloc

        # Send the DNS query to see if the link_domain_name has a CNAME record
        query=DNSRecord.question(link_domain_name)
        dns_response = DNSRecord.parse(
            query.send(
                self.dns_server,
                53, 
                False,
                timeout=self.dns_timeout
            )
        )
        
        # Create an array of CNAME records returned by the DNS query
        jsitems = list()

        # Check if the first record is a CNAME
        for record in dns_response.rr:
            if QTYPE[record.rtype] == 'CNAME':
                pointer=str(record.rdata)
                fld_pointer=get_fld(pointer)
                self.logger.debug("The parent domain %s contains a link to domain %s. This link domain has a CNAME entry pointing to %s (subdomain of %s))" % (parent_domain_name,link_domain_name,pointer,fld_pointer))
                
                # Check if the first level domain is registered
                query_cname=DNSRecord.question(fld_pointer)
                cname_response=DNSRecord.parse(
                    query_cname.send(
                        self.dns_server,
                        53,
                        False,
                        timeout=self.dns_timeout
                    )
                )
                
                jsitem=JsLink()
                jsitem['hijackable_domain']="%s (%s)" % (link_domain_name, pointer)
                jsitem['parent_domain']=parent_domain_name
                jsitem['script_domain_fld']=fld_pointer
                jsitem['hijackable']=False
                jsitem["cname_hijackable"]=False
                jsitem['embedded_url']=link_url
                jsitem['parent_url']=parent_response_url
                jsitem['type']=link_type
                
                # Check potential hijacks
                if RCODE[cname_response.header.rcode] == 'NXDOMAIN':
                    self.logger.warning("The parent domain %s embed a remote source from %s. The first level domain CNAME record points to %s with FLD %s. The pointed to the FLD domain is not registered!" % (parent_domain_name,link_domain_name, pointer, fld_pointer))
                    jsitem["hijackable"]=True
                    jsitem["cname_hijackable"]=True
                    self.discord.notify_takeover("CNAME Domain Hijack Detected (direct)!",jslink=jsitem)
                elif ("s3.amazonaws.com" in pointer.lower()):
                    # Check the S3 bucket exists. If not, we can create it ourselves
                    s3_response=requests.get(pointer,headers=self.headers,verify=False)
                    if (s3_response.status_code == 404 and "NoSuchBucket" in s3_response.text):
                        jsitem['hijackable']=True
                        jsitem["cname_hijackable"]=True
                        self.logger.warning("Parent domain %s includes a remote source from %s. This source points to the S3 bucket %s, which is not registered. You can takeover the parent domain!" % (parent_domain_name, link_domain_name, pointer))
                        self.discord.notify_takeover("CNAME Domain Hijack Detected (S3)!",jslink=jsitem)
                    else:
                        self.logger.debug("The pointer %s is hoste in an S3 bucket, but it is currently taken")
                elif ("bitbucket.io" in pointer.lower()):
                    bb_response=requests.get(pointer,headers=self.headers,verify=False)
                    if (bb_response.text == "Repository not found" and bb_response.status_code == 404):
                        jsitem['hijackable']=True
                        jsitem["cname_hijackable"]=True
                        self.logger.warning("Parent domain %s includes a remote source from %s. This source points to the bitbucket %s, which is not registered. You can takeover the parent domain!" % (parent_domain_name, link_domain_name, pointer))
                        self.discord.notify_takeover("CNAME Domain Hijack Detected (bitbucket)!",jslink=jsitem)
                    else:
                        self.logger.debug("The pointer %s is hoste in an bitbucket, but it is currently taken")
                elif ("hatenablog.com" in pointer.lower()):
                    hatena_response=requests.get(pointer,headers=self.headers,verify=False)
                    if (hatena_response.text == "Blog is not found" and hatena_response.status_code == 404):
                        jsitem['hijackable']=True
                        jsitem["cname_hijackable"]=True
                        self.logger.warning("Parent domain %s includes a remote source from %s. This source points to the hatenablog %s, which is not registered. You can takeover the parent domain!" % (parent_domain_name, link_domain_name, pointer))
                        self.discord.notify_takeover("CNAME Domain Hijack Detected (hatenablog)!",jslink=jsitem)
                    else:
                        self.logger.debug("The pointer %s is hoste in an hatenablog, but it is currently taken")
                elif ("helpjuice.com" in pointer.lower()):
                    hj_response=requests.get(pointer,headers=self.headers,verify=False)
                    if (hj_response.text == "We could not find what you're looking for" and hj_response.status_code == 404):
                        jsitem['hijackable']=True
                        jsitem["cname_hijackable"]=True
                        self.logger.warning("Parent domain %s includes a remote source from %s. This source points to the helpjuice %s, which is not registered. You can takeover the parent domain!" % (parent_domain_name, link_domain_name, pointer))
                        self.discord.notify_takeover("CNAME Domain Hijack Detected (helpjuice)!",jslink=jsitem)
                    else:
                        self.logger.debug("The pointer %s is hoste in an helpjuice bucket, but it is currently taken")
                elif ("helpscoutdocs.com" in pointer.lower()):
                    hs_response=requests.get(pointer,headers=self.headers,verify=False)
                    if (hs_response.text == "No settings were found for this company" and hs_response.status_code == 404):
                        jsitem['hijackable']=True
                        jsitem["cname_hijackable"]=True
                        self.logger.warning("Parent domain %s includes a remote source from %s. This source points to the helpscouts %s, which is not registered. You can takeover the parent domain!" % (parent_domain_name, link_domain_name, pointer))
                        self.discord.notify_takeover("CNAME Domain Hijack Detected (helpscoutdocs)!",jslink=jsitem)
                    else:
                        self.logger.debug("The pointer %s is hoste in an helpscoutdocs bucket, but it is currently taken")
                else:
                    self.logger.debug(f"CNAME Hijack was not detected for parent domain {parent_domain_name}")

                # Append the jsitem to the hijackable_jsitems list
                jsitems.append(jsitem)
        
        return jsitems
    
    def detect_unregistered_domain_hijack(
            self,
            response: Response,
            safe_fdl: set,
            hijackable_fdl: set,
            source_link,
            link_type: LinkType = LinkType.UNKNOWN
        ) -> JsLink:
        """
        Detect if the source link is a hijackable domain because it returns an NXDOMAIN.
        """
        source_attr = source_link.attrib["src"].strip()
        respp=urlparse(response.url)
        jslp=urlparse(source_attr)
        fld=get_fld(source_attr)
        jsitem=JsLink()
        
        # Check if not already explored or is the same domain as this response URL 
        if (fld in safe_fdl):
            # self.logger.debug("First level domain %s already explored and is registered. Skipping." % fld)
            pass
        elif (fld in hijackable_fdl):
            # If the domain is already in the hijackable_fdl, it means it has been processed
            jsitem=JsLink()
            jsitem["parent_url"]=response.url
            jsitem["hijackable_domain"]=jslp.netloc
            jsitem["script_domain_fld"]=fld
            jsitem["embedded_url"]=source_attr
            jsitem["parent_domain"]=respp.netloc
            jsitem["hijackable"]=True
            jsitem["cname_hijackable"]=False
            jsitem["type"]=link_type

            self.logger.warning("First Level Domain %s (of domain %s) already explored and was not registered!" % (fld,jslp.netloc))
            self.logger.warning(f"Item: {jsitem}")

        elif (jslp.netloc != respp.netloc and jslp.netloc != ""):
            self.logger.debug("First level domain %s. Exploring for the first time." % fld)
            jsitem=JsLink()
            jsitem["parent_url"]=response.url
            jsitem["hijackable_domain"]=jslp.netloc
            jsitem["script_domain_fld"]=fld
            jsitem["embedded_url"]=source_attr
            jsitem["parent_domain"]=respp.netloc
            jsitem["hijackable"]=False
            jsitem["cname_hijackable"]=False
            jsitem["type"]=link_type
            
            self.logger.debug("Querying first level domain %s to server %s" % (fld,self.settings.get("DNS_SERVER")))
            query=DNSRecord.question(fld)
            dns_response = DNSRecord.parse(
                query.send(
                    self.dns_server, 
                    53, 
                    False, 
                    timeout=self.dns_timeout
                )
            )
            if RCODE[dns_response.header.rcode] == 'NXDOMAIN':
                # Now, check if the domain is not registered using RDAP
                if not self.whois_rdap.is_registered(fld):
                    if not self.whois_classic.is_registered(fld):
                        jsitem["hijackable"]=True
                        self.logger.warning("First Level Domain %s (of domain %s) not registered" % (fld,jslp.netloc))
                        self.logger.warning("Used as script source in %s (%s)" % (response.url,source_attr))
                    else:
                        jsitem["hijackable"]=False
                        self.logger.info("First Level Domain %s (of domain %s) is registered (not found with , though)" % (fld,jslp.netloc))
                        self.logger.info("Used as script source in %s (%s)" % (response.url,source_attr))
                else:
                    jsitem["hijackable"]=False
                    self.logger.info("First Level Domain %s (of domain %s) is registered" % (fld,jslp.netloc))
                    self.logger.info("Used as script source in %s (%s)" % (response.url,source_attr))
            else:
                self.logger.debug("Third-party domain '%s' (%s) embedded in '%s', but is registered" % (fld, jslp.netloc,respp.netloc))
        # else:
        #     self.logger.debug("Source link %s is not a valid domain or is the same as the response URL %s" % (source_attr, response.url))

        return jsitem
