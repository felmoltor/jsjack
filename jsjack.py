#!/usr/bin/env python3
import argparse
import logging
import sys

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from  subdomain_takeover.spiders.takeover import TakeoverSpider  

def get_logging_level(level_str: str) -> int:
    return {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARN': logging.WARNING,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }.get(level_str.upper(), logging.INFO)

def main():
    parser = argparse.ArgumentParser(description="Run Scrapy takeover spider with options.")
    parser.add_argument('-u', '--urls', required=True)
    parser.add_argument('-d', '--dns')
    parser.add_argument('-A', '--allow-fld', action='store_true')
    parser.add_argument('-S', '--scrapeops-key')
    parser.add_argument('-D', '--discord-webhook')
    parser.add_argument('-L', '--logging-level', choices=['DEBUG','INFO','WARN','ERROR','CRITICAL'])
    parser.add_argument('-E', '--max-depth')
    parser.add_argument('-I', '--max-items')
    parser.add_argument('-P', '--max-pages')
    args = parser.parse_args()

    # Get and modify Scrapy settings
    settings = get_project_settings()
    if args.logging_level:
        settings.set('LOG_LEVEL', args.logging_level.upper())
    if args.scrapeops_key:
        settings.set('SCRAPEOPS_KEY', args.scrapeops_key)
    if args.discord_webhook:
        settings.set('DISCORD_WEBHOOK', args.discord_webhook)
    if args.max_depth:
        settings.set('DEPTH_LIMIT', int(args.max_depth))
    if args.max_pages:
        settings.set('MAX_PAGES_PER_FLD', int(args.max_pages))
    if args.max_items:
        settings.set('MAX_ITEMS_PER_FLD', int(args.max_items))
    if args.dns:
        settings.set('DNS_SERVER', args.dns)

    process = CrawlerProcess(settings)


    spider_kwargs = {
        'urls': args.urls,
    }
    if args.allow_fld:
        spider_kwargs['allow_fld'] = True

    process.crawl(TakeoverSpider, **spider_kwargs)
    process.start()

if __name__ == '__main__':
    main()
