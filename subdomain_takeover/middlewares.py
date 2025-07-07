# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

# useful for handling different item types with a single interface
from tldextract import extract as tld_extract
from subdomain_takeover.items import JsLink
from scrapy.exceptions import IgnoreRequest
from subdomain_takeover.spiders.takeover import TakeoverSpider
from urllib.parse import urlparse

def get_fld(url):
    ext=tld_extract(url)
    return f"{ext.domain}.{ext.suffix}"

class DomainLimitDownloaderMiddleware:
    def process_request(self, request, spider: TakeoverSpider):
        fld = get_fld(request.url)

        # Limits
        items_limit = spider.settings.getint('MAX_ITEMS_PER_FLD', 150)
        pages_limit = spider.settings.getint('MAX_PAGES_PER_FLD', 20)

        spider.pages_counter[fld]+=1
        
        # Get current pages counter
        pages_count = spider.pages_counter.get(fld)
        if pages_count <= pages_limit:
            # spider.logger.debug(f"[DomainLimitDownloaderMiddleware] Continue with {request.url} (pages limit ok for {fld} ({pages_count} < {pages_limit})")
            return None
        else:
            spider.logger.debug(f"[DomainLimitDownloaderMiddleware] Skipping {request.url} (pages limit reached for {fld} ({pages_count} > {pages_limit})")
            raise IgnoreRequest
        
# For clarity, I moved from the function of the spider:
# def link_to_file(self,path):
#     """Check if the link is to a file to prevent following it"""
#     extension=path.split("?")[0].split(".")[-1]
#     if extension.lower() in ["msi","exe","tar.gz","tgz","xz","tar.bz","zip","rar","doc","docx","pdf","xls","xlsx","ppt","pptx","jpg","jpeg","png","tiff","svg","woff","mp4","avi","mpeg","mpg","mp3","run"]:
#         return True
#     else:
#         return False

# TODO: Replace this middleware with a HEAD request inspection and if the content is 'application/*' it means is a binary file
class BlockBinaryFilesMiddleware:
    def process_request(self, request, spider: TakeoverSpider):
        binary_extensions = (
            ".exe", ".msi", ".apk", ".bat", ".cmd", ".gadget", ".jar", ".pif",
            ".pyc", ".pyo", ".sh", ".vb", ".vbs", ".wsf", ".run", ".bin", ".cgi",
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".lz", ".lzma", ".z", ".iso",
            ".dmg", ".vmdk", ".vdi", ".img", ".cue", "pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma",
            ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".mpeg", ".mpg", ".3gp",
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svgz",
            ".ttf", ".otf", ".woff", ".woff2", ".eot", ".fon", ".applet", ".dat"
        )
        rup = urlparse(request.url)
        if rup.path.lower().endswith(binary_extensions):
            spider.logger.warning(f"Blocked download. Request is a binary file: {request.url}")
            raise IgnoreRequest("Blocked download. It is binary file: {request.url}")
        return None