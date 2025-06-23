# Cache class to cache HTTP responses with pruning capabilities
import os
import heapq
from scrapy.extensions.httpcache import FilesystemCacheStorage
from ..takeover import TakeoverSpider

class PrunableFilesystemCacheStorage(FilesystemCacheStorage):
    def __init__(self, settings):
        super().__init__(settings)
        self.cache_dir = settings.get('HTTPCACHE_DIR', '.scrapy/httpcache')
        self.max_files = settings.getint('HTTPCACHE_MAX_FILES', 1024)  # 0 = no limit
        self.max_size_bytes = settings.getint('HTTPCACHE_MAX_SIZE', 100 * 1024 * 1024)  # 0 = no limit

    def open_spider(self, spider: TakeoverSpider):
        super().open_spider(spider)
        self._prune_cache(spider)

    def _prune_cache(self, spider):
        """Prune the cache to ensure it does not exceed max_files and max_size_bytes."""
        spider.logger.info(f"[HTTPCACHE] Pruning cache {self.cache_dir}...")
        if not os.path.exists(self.cache_dir):
            return

        spider.logger.info('[HTTPCACHE] Cache exists...')

        files = []
        total_size = 0

        for root, _, filenames in os.walk(self.cache_dir):
            for f in filenames:
                full_path = os.path.join(root, f)
                try:
                    stat = os.stat(full_path)
                    total_size += stat.st_size
                    heapq.heappush(files, (stat.st_mtime, full_path))  # oldest first
                except Exception:
                    continue

        spider.logger.info(f"[HTTPCACHE] Found {len(files)} files with total size {total_size} bytes in cache")

        if self.max_files and len(files) > self.max_files:
            self._remove_oldest(files, len(files) - self.max_files, spider)

        if self.max_size_bytes and total_size > self.max_size_bytes:
            removed = 0
            while total_size > self.max_size_bytes and files:
                _, path = heapq.heappop(files)
                try:
                    size = os.stat(path).st_size
                    os.remove(path)
                    total_size -= size
                    removed += 1
                except Exception:
                    continue
            spider.logger.info(f"[HTTPCACHE] Pruned {removed} files to stay under {self.max_size_bytes} bytes")

    def _remove_oldest(self, files, count, spider):
        removed = 0
        for _ in range(count):
            if files:
                _, path = heapq.heappop(files)
                try:
                    os.remove(path)
                    removed += 1
                except Exception:
                    continue
        spider.logger.info(f"[HTTPCACHE] Pruned {removed} old cache files to stay under limit")
