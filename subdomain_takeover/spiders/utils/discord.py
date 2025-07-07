import socket
from datetime import datetime
import requests
import logging
from subdomain_takeover.items import JsLink

class TakeoverDiscordBot:
    def __init__(self, webhook_url: str, logger=None, use_proxies=False, settings=None):
        self.logger = logger or logging.getLogger(__name__)
        self.use_proxies = use_proxies
        self.settings = settings or {}
        self.webhook_url = webhook_url
        self.hostname = socket.gethostname()

    def notify_takeover(self, msg_title: str, jslink: JsLink):
        """
        Notify about a domain takeover via Discord webhook.
        :param msg_title: Title of the message to be sent.
        :param jslink: The JavaScript item containing details about the domain takeover.
        """
        if self.webhook_url is None:
            self.logger.warning("Discord webhook URL is not set. Skipping notification.")
        else:
            now = datetime.now()
            date=now.strftime("%d-%m-%Y")
            time=now.strftime("%H:%M:%S")
            data={
                "username": f"{self.hostname} - Domain Takeover Bot"
            }
            data["embeds"]=[
                {
                    "description" : "Domain Takeover Notification",
                    "title" : msg_title,
                    "fields": [
                        {
                            "name": "Date",
                            "value": f"{date}-{time}"
                        },
                        {
                            "name": "Parent Domain",
                            "value": str(jslink.get("parent_domain"))
                        },
                        {
                            "name": "Parent URL",
                            "value": str(jslink.get("parent_url"))
                        },
                        {
                            "name": "Embedded Domain",
                            "value": "%s (%s)" % (jslink.get("hijackable_fld"), jslink.get("hijackable_domain"))
                        },
                        {
                            "name": "Script",
                            "value": str(jslink.get("embedded_url"))
                        },
                        {
                            "name": "Link type",
                            "value": str(jslink.get("type"))
                        }
                    ]
                }
            ]
            if (self.use_proxies):
                requests.post(url=self.webhook_url,json=dict(data),proxies=self.settings.get("PROXIES"),verify=False)
            else:
                requests.post(url=self.webhook_url,json=dict(data))

    def notify_status(
            self,
            status: str,
            file_name: str,
            registered_domains: int,
            orphan_domains: int,
            scrapped_pages: int
        ):
        """
        Notify about the status of the crawler via Discord.
        :param status: status message to be sent in the title of the Discord message.
        """
        if self.webhook_url is None:
            self.logger.warning("Discord webhook URL is not set in settings. Skipping notification.")
        else:
            now = datetime.now()
            date=now.strftime("%d-%m-%Y")
            time=now.strftime("%H:%M:%S")
            
            data={
                "username": f"{socket.gethostname()} - Domain Takeover Bot"
            }
            data["embeds"]=[
                {
                    "description" : "Domain Takeover Status",
                    "title" : status,
                    "fields": [
                        {
                            "name": "Date",
                            "value": f"{date}-{time}"
                        },
                        {
                            "name": "File name",
                            "value": file_name
                        },
                        {
                            "name": "Domains Explored",
                            "value": f"{registered_domains+orphan_domains}"
                        },
                        {
                            "name": "Scrapped pages",
                            "value": f"{scrapped_pages}"
                        },
                        {
                            "name": "Hijackable Domains",
                            "value": f"{orphan_domains}"
                        }                        
                    ]
                }
            ]
            if (self.use_proxies):
                requests.post(url=self.webhook_url,json=dict(data),proxies=self.settings.get("PROXIES"),verify=False)
            else:
                requests.post(url=self.webhook_url,json=dict(data))
