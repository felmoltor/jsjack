import sqlite3
import logging
from subdomain_takeover.items import JsLink

class TakeoverDatabase:
    def __init__(self, settings, logger=None):
        self.settings = settings
        self.db_name = self.settings.get("DATABASE_FILE", "takeover.db")
        self.connection = sqlite3.connect(self.db_name)
        self.cursor = self.connection.cursor()
        self.logger = logger or logging.getLogger(__name__)
        self.init_database()

    def insert_subdomain(self, subdomain, status):
        self.cursor.execute('''
            INSERT INTO subdomains (subdomain, status) VALUES (?, ?)
        ''', (subdomain, status))
        self.connection.commit()

    def init_database(self):
        """
        Initialize the sqlite3 database to store the items.
        """
        # Check if the database is initialized, if not, create the table
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS js_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_url TEXT,
                parent_domain TEXT,
                hijackable_domain TEXT,
                hijackable BOOLEAN,
                embedded_url TEXT,
                domain_embedding TEXT,
                cname_hijackable BOOLEAN,
                hijackable_fld BOOLEAN,
                type INTEGER
            )
        ''')
        self.conn.commit()
        self.logger.info("Database initialized at %s" % self.db_name)

    def save_item_to_database(self, item: JsLink):
        """
        Save the JavaScript to the sqlite3 database.
        """
        if item:
            # Check if the item is already in the database
            self.cursor.execute('''
                SELECT COUNT(*) FROM js_links WHERE parent_url = ? AND embedded_url = ?
            ''', (item.get('parent_url'), item.get('embedded_url')))
            count = self.cursor.fetchone()[0]
            if count > 0:
                self.logger.debug("Item already exists in the database, skipping: %s" % item)
            else:
                # Get the database connection object and save the item 
                self.logger.debug(f"Saving item to database: {item}")
                self.cursor.execute('''
                    INSERT INTO js_links (
                        parent_url,
                        parent_domain,
                        hijackable_domain,
                        hijackable,
                        embedded_url,
                        domain_embedding,
                        cname_hijackable,
                        hijackable_fld,
                        type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item.get('parent_url'),
                    item.get('parent_domain'),
                    item.get('hijackable_domain'),
                    item.get('hijackable', False),
                    item.get('embedded_url'),
                    item.get('domain_embedding'),
                    item.get('cname_hijackable', False),
                    item.get('hijackable_fld', False),
                    int(item.get('type').value)
                ))
        else:
            self.logger.warning("Attempted to save an empty item to the database.")

    def save_items_to_database(self, items):
        """
        Save multiple JavaScript items to the sqlite3 database in a single transaction.
        """
        if items:
            self.logger.debug(f"Saving {len(items)} items to database")
            for item in items:
                # Print item details for debugging
                self.logger.debug(f"Processing item: {item}")
                self.save_item_to_database(item)
            self.connection.commit()
            self.logger.info(f"{len(items)} items saved to database successfully.")
        else:
            self.logger.warning("Attempted to save an empty list of items to the database.")

    def get_hijackable_links(self):
        """
        Retrieve all hijackable links from the database.
        """
        self.cursor.execute('''
            SELECT * FROM js_links WHERE hijackable = 1
        ''')
        return self.cursor.fetchall()
    
    def get_safe_links(self):
        """
        Retrieve all hijackable links from the database.
        """
        self.cursor.execute('''
            SELECT * FROM js_links WHERE hijackable <> 1
        ''')
        return self.cursor.fetchall()
    
    def get_all_links(self):
        """
        Retrieve all links from the database.
        """
        self.cursor.execute('''
            SELECT * FROM js_links
        ''')
        return self.cursor.fetchall()
        
    def close(self):
        self.connection.close()