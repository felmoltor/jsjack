# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy import Item,Field
from enum import Enum,auto

class LinkType(Enum):
    UNKNOWN=auto()
    IFRAME=auto()
    FRAME=auto()
    DIRECT=auto()
    JAVASCRIPT=auto()

class JsLink(Item):
    hijackable = Field()        # Boolean indicating if the domain is hijackable (e.g. True)
    cname_hijackable = Field()  # Boolean indicating if the cname is hijackable (e.g. True)

    parent_url = Field()        # The URL of the parent page containing the script (e.g. https://www.google.com/search/bla?q=123)
    parent_domain=Field()       # The full domain of the parent page (e.g. www.google.com)
    hijackable_domain = Field() # The full domain of the script or cname that can be hijacked because it's not registered (e.g. www.hijackable.com)
    embedded_url = Field()      # The full URL of the script that can be hijacked (e.g. https://www.hijackable.com/script.js)
    script_domain_fld=Field()   # The First level domain of the script that can be hijacked (e.g. hijackable.com)
    type=Field()                # Type of inclusion of this script in the parent page (e.g. LinkType.IFRAME, LinkType.FRAME, LinkType.DIRECT, LinkType.JAVASCRIPT)

class SubdomainTakeoverItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass
