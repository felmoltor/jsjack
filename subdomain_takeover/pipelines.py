# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from .items import JsLink
import json
from datetime import datetime
from subdomain_takeover.spiders.takeover import TakeoverSpider

class SubdomainTakeoverJsonPipeline:
    def __init__(self) -> None:
        d = datetime.now().strftime("%d%m%Y_%H%M%S")
        self.safe_links_file = f"output/{d}_safe_links.json"
        self.orphan_links_file = f"output/{d}_orphan_links.json"
        self.safe_domains_file = 'output/safe_domains.txt'
        self.orphan_domains_file = 'output/hijackable_domains.txt'
        
        # Read this run json files
        self.sfile = open(self.safe_links_file, 'w')
        self.ofile = open(self.orphan_links_file, 'w')
        
        # Read the global txt files
        self.hijackable_domains = set(open(self.orphan_domains_file, 'r').readlines())
        self.safe_domains = set(open(self.safe_domains_file, 'r').readlines())

        self.ofile.write('[')
        self.sfile.write('[')
        self.ofirst_item = True
        self.sfirst_item = True

    def close_spider(self, spider):
        self.sfile.write(']')
        self.sfile.close()
        self.ofile.write(']')
        self.ofile.close()

    def process_item(self, item: JsLink, spider: TakeoverSpider):
        if isinstance(item, JsLink):
            item_dict = dict(item)
            if 'type' in item_dict and hasattr(item_dict['type'], 'name'):
                item_dict['type'] = item_dict['type'].name

            if item_dict['hijackable']:
                if not self.ofirst_item:
                    self.ofile.write(',\n')
                else:
                    self.ofirst_item = False
                json.dump(item_dict, self.ofile)
                
                # Save the hijackable domain in the global txt file
                if (item_dict['script_domain_fld'] + '\n') not in self.hijackable_domains:
                    self.hijackable_domains.add(item_dict['script_domain_fld'] + '\n')
                    # Save the registered domain in the global txt file
                    with open('output/hijackable_domains.txt', 'a') as f:
                        f.write(f"{item_dict['script_domain_fld']}\n")
            else:
                if not self.sfirst_item:
                    self.sfile.write(',\n')
                else:
                    self.sfirst_item = False
                json.dump(item_dict, self.sfile)

                # Save the registered domain in the global txt file
                if (item_dict['script_domain_fld'] + '\n') not in self.safe_domains:
                    self.safe_domains.add(item_dict['script_domain_fld'] + '\n')
                    # Save the registered domain in the global txt file
                    with open('output/safe_domains.txt', 'a') as f:
                        f.write(f"{item_dict['script_domain_fld']}\n")
        return item
    
class SubdomainTakeoverDiscordPipeline:
    """
    This pipeline is used to send messages to a Discord channel.
    Will only send notifications if the item is an instance of JsLink and hijackable is True.
    """
    def process_item(self, item: JsLink, spider: TakeoverSpider):
        if isinstance(item, JsLink) and item['hijackable']:
            # Save the notification to the file notifications.txt
            if not self.already_notified(item, spider):
                spider.discord.notify_takeover("Subdomain Takeover Detected!", item)
                with open('output/notifications.txt', 'a') as f:
                    f.write(f"{item['parent_domain']}<=>{item['hijackable_domain']}\n")
            # else:
            #     spider.logger.info("Item has already been notified, skipping Discord notification.")
        # else:
        #     spider.logger.info("Item is not hijackable or not an instance of JsLink, skipping Discord notification.")
        return item
    
    def already_notified(self, item: JsLink, spider: TakeoverSpider):
        """
        Check if the item has already been notified.
        This is a placeholder for any logic you might want to implement to avoid duplicate notifications.
        """
        # We read the file notifications.txt and see if the item has already been notified
        # The file contains a pair of parent_fdl and embedded_fld separated by the string '<=>'
        notified_file = 'output/notifications.txt'
        try:
            with open(notified_file, 'r') as f:
                notified_items = f.readlines()
                for line in notified_items:
                    parent_fld, embedded_fld = line.strip().split('<=>')
                    if parent_fld == item['parent_domain'] and embedded_fld == item['hijackable_domain']:
                        return True
        except FileNotFoundError:
            # If the file does not exist, we assume no items have been notified yet
            return False
        
