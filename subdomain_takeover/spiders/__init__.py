# This package will contain the spiders of your Scrapy project
#
# Please refer to the documentation for information on how to create and manage
# your spiders.

from subdomain_takeover.spiders.utils.colored import Colored
from subdomain_takeover.spiders.utils.discord import TakeoverDiscordBot
from subdomain_takeover.spiders.utils.whois import WhoisRDAP
from subdomain_takeover.spiders.utils.hijacker import DomainHijacker