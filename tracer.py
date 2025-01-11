#!/usr/bin/env python3
import subprocess
import re
import geoip2.database
from pathlib import Path
from datetime import datetime
import sys

CITY_DB_PATH = "GeoLite2-City.mmdb"
ASN_DB_PATH = "GeoLite2-ASN.mmdb"


class LocalGeoTraceroute:
    def __init__(self, city_db_path, asn_db_path):
        """
        Initialize with paths to MaxMind GeoLite2 City and ASN databases
        """
        self.city_db_path = Path(city_db_path)
        self.asn_db_path = Path(asn_db_path)
        
        if not self.city_db_path.exists():
            raise FileNotFoundError(f"GeoLite2 City database not found at {city_db_path}")
        if not self.asn_db_path.exists():
            raise FileNotFoundError(f"GeoLite2 ASN database not found at {asn_db_path}")
        
        self.ip_pattern = r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}'
        self.city_reader = geoip2.database.Reader(str(self.city_db_path))
        self.asn_reader = geoip2.database.Reader(str(self.asn_db_path))

    def __del__(self):
        """Ensure the database readers are closed"""
        if hasattr(self, 'city_reader'):
            self.city_reader.close()
        if hasattr(self, 'asn_reader'):
            self.asn_reader.close()

    def get_location(self, ip):
        """Query IP geolocation data from local MaxMind City database"""
        try:
            response = self.city_reader.city(ip)
            return {
                'city': response.city.name or 'N/A',
                'region': response.subdivisions.most_specific.name if response.subdivisions else 'N/A',
                'country': response.country.name or 'N/A',
                'lat': response.location.latitude,
                'lon': response.location.longitude
            }
        except Exception:
            return None

    def get_asn(self, ip):
        """Query ASN data from local MaxMind ASN database"""
        try:
            response = self.asn_reader.asn(ip)
            return {
                'asn': response.autonomous_system_number,
                'org': response.autonomous_system_organization
            }
        except Exception:
            return None

    def format_hop(self, hop_number, ip, location, asn_info, raw_output):
        """Format a single hop's information"""
        BOLD = '\033[1m'
        BLUE = '\033[94m'
        GREEN = '\033[92m'
        RESET = '\033[0m'
        
        output = []
        output.append(f"\n{BOLD}{BLUE}#{hop_number} {ip}{RESET}")
        
        if location:
            output.append(f"   {location['city']}, {location['region']}, {location['country']}")
            output.append(f"   ({location['lat']}, {location['lon']})")
        
        if asn_info:
            output.append(f"   {GREEN}AS{asn_info['asn']} - {asn_info['org']}{RESET}")
        
        if not location and not asn_info:
            output.append("   Private IP or not found in database")
            
        return "\n".join(output)

    def resolve_target(self, destination):
        """Resolve target hostname to IP"""
        try:
            import socket
            return socket.gethostbyname(destination)
        except Exception:
            return None

    def run_traceroute_realtime(self, destination):
        """Run traceroute and process results in real-time"""
        BOLD = '\033[1m'
        BLUE = '\033[94m'
        GREEN = '\033[92m'
        RESET = '\033[0m'

        target_ip = self.resolve_target(destination)
        location = self.get_location(target_ip) if target_ip else None
        asn_info = self.get_asn(target_ip) if target_ip else None

        print("\nGeo-Enhanced Traceroute")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Target: {destination}")
        if target_ip:
            print(f"Resolved IP: {BOLD}{target_ip}{RESET}")
            if location:
                print(f"Location: {location['city']}, {location['region']}, {location['country']}")
            if asn_info:
                print(f"Network: {GREEN}AS{asn_info['asn']} - {asn_info['org']}{RESET}")
        print("-" * 45)
        
        try:
            # Determine the command based on OS
            if subprocess.os.name == 'nt':  # Windows
                cmd = ['tracert', destination]
            else:  # Unix/Linux/MacOS
                cmd = ['traceroute', '-n', destination]
            
            # Start the traceroute process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            hop_number = 0
            # Process output in real-time
            for line in process.stdout:
                # Skip header lines
                if 'traceroute to' in line.lower() or 'tracing route to' in line.lower():
                    continue
                    
                ip_match = re.search(self.ip_pattern, line)
                if ip_match:
                    hop_number += 1
                    ip = ip_match.group()
                    location = self.get_location(ip)
                    asn_info = self.get_asn(ip)
                    
                    # Print formatted hop information immediately
                    print(self.format_hop(hop_number, ip, location, asn_info, line.strip()))
                    sys.stdout.flush()  # Ensure output is displayed immediately
                
            # Wait for process to complete
            process.wait()
            if process.returncode != 0:
                print("\nWarning: Traceroute process ended with non-zero status")
                
        except Exception as e:
            print(f"\nError during traceroute: {str(e)}")
            return False
            
        return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python tracer.py <destination>")
        print("Example: python tracer.py google.com")
        sys.exit(1)
    
    destination = sys.argv[1]
    
    try:
        tracer = LocalGeoTraceroute(CITY_DB_PATH, ASN_DB_PATH)
        tracer.run_traceroute_realtime(destination)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()