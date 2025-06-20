JSJack
======

# What is JSJack
JSJack is a tool that explores a list of web pages and retrieves all links to JavaScript files externally hosted.
It search for files hosted within the `script`, `frame`, and `iframe` tags. For each of those, it check wether the domain where the script is hosted is registered by doing a DNS query and a RDAP query. If the domain is not registered, it shows an alert in the console, and optionally sends an alert to a Discord webhook.

You can provide a [Scrape Ops](https://scrapeops.io/) key to use the platform during the crawling.

You can also provide a [Discord webhook](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks) to receive the notifications when an orphan JavaScript file has been detected.

# Installation
## Docker
Clone the project and provide the arguments
```bash
git clone https://github.com/felmoltor/jsjack
docker build -t jsjack:latest .
docker run -v $PWD/input/:/app/input/ -it --rm  jsjack  -h
docker run -v $PWD/input/:/app/input/ -v $PWD/output/:/app/output/ -it --rm  jsjack -u input/targets.txt --discord-webhook 'https://discord.com/api/webhooks/<id> --scrapeops-key <key>
```

Alternatively, you can add to a .env file the variables DISCORD_WEBHOOK and SCRAPEOPS_KEY in the folder 'spiders' instead of providing it via arguments:
```bash
echo 'SCRAPEOPS_KEY=yourkey' >> spiders/.env
echo 'DISCORD_WEBHOOK=https://discord.com/api/webhooks/<id>' >> spiders/.env
docker run -v $PWD/input/:/app/input/ -v $PWD/output/:/app/output/ -v $PWD/.env:/app/spiders/.env -it --rm  jsjack -u input/targets.txt
```

I've also published the image in the GitHub registry, so instead of cloning the repository:
```bash
docker pull ghcr.io/felmoltor/jsjack/jsjack:latest 
docker image tag ghcr.io/felmoltor/jsjack/jsjack:latest jsjack
docker run -v $PWD/input/:/app/input/ -v $PWD/output/:/app/output/ -it --rm  jsjack -u input/targets-urls.txt
```

## Output
The tool will export the scrapped items in the folder output in JSON format. The following files would appear here:
* **hijackable_domains.txt**: global list of orphan or hijackable domains where we have already found some scripts to be hosted.
* **safe_domains.txt**: global list of registered domains that host scripts. You can not register these domains.
* **[date]_orphan_links.json**: The JavaScript items scrapped in this execution. These are scripts that are considered orphan and you can take over by registering the domain where they are hosted. It contains more details that the global txt file.
* **[date]_safe_links.json**:The JavaScript items scrapped in this execution. These are scripts that are considered safe and you cannot take over by registering the domain where they are hosted. It contains more details that the global txt file.

## Crawling
The current parameters of the Scrapy spider are considered gentle, only sending 5 concurrent requests per domain or per IP ([CONCURRENT_REQUESTS_PER_DOMAIN](https://docs.scrapy.org/en/latest/topics/settings.html#concurrent-requests-per-domain), [CONCURRENT_REQUESTS_PER_IP](https://docs.scrapy.org/en/latest/topics/settings.html#std-setting-CONCURRENT_REQUESTS_PER_IP)). Additionally, it will only crawl a maximum depth of 2 ([DEPTH_LIMIT](https://docs.scrapy.org/en/latest/topics/settings.html#depth-limit)).

You can modify these settings, but, please, keep them low so you don't affect the target web applications negatively.

You can also limit the maximum number of pages scanned per web (guided by the first level domain of the page) by setting the custom variables MAX_PAGES_PER_FLD and MAX_ITEMS_PER_FLD to speed up the process. 

All these settings can also be provided on runtime with their corresponding parameters of the 'Crawling limits' section:

```bash
usage: jsjack.py [-h] -u URLS [-d DNS] [-A] [-S SCRAPEOPS_KEY] [-D DISCORD_WEBHOOK] [-E MAX_DEPTH] [-I MAX_ITEMS] [-P MAX_PAGES] ...

Wrapper to run the Scrapy takeover spider with custom arguments.

positional arguments:
  extra                 Extra arguments to pass to Scrapy

options:
  -h, --help            show this help message and exit
  -u URLS, --urls URLS  Path to the URLs file (required)
  -d DNS, --dns DNS     DNS server to use to resolve domains
  -A, --allow-fld       Allow first-level domain allowlist
  -S SCRAPEOPS_KEY, --scrapeops-key SCRAPEOPS_KEY
                        ScrapeOps API key (overrides settings)
  -D DISCORD_WEBHOOK, --discord-webhook DISCORD_WEBHOOK
                        Discord webhook URL (overrides settings)

Crawling limits:
  Limit the crawling time on target domains

  -E MAX_DEPTH, --max-depth MAX_DEPTH
                        Maximum depth to crawl a website
  -I MAX_ITEMS, --max-items MAX_ITEMS
                        Maximum number of items to crawl per website (counted by first level domain of the website)
  -P MAX_PAGES, --max-pages MAX_PAGES
                        Maximum number of pages to crawl per website (counted by first level domain of the website)
```