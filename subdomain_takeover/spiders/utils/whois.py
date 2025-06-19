import whoisit
import whois

class WhoisRDAP:
    def __init__(self):
        whoisit.bootstrap()

    def fetch_whois_data(self, domain: str):
        try:
            return whoisit.domain(domain)
        except Exception as e:
            return {}
        
    def is_registered(self, domain: str) -> bool:
        whois_data = self.fetch_whois_data(domain)
        if whois_data and 'name' in whois_data:
            return True
        return False
    
class WhoisClassic:
    def fetch_whois_data(self, domain: str):
        try:
            return whois.whois(domain)
        except Exception as e:
            return {}
        
    def is_registered(self, domain: str) -> bool:
        whois_data = self.fetch_whois_data(domain)
        if whois_data and 'domain_name' in whois_data:
            return True
        return False