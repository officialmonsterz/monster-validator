#!/usr/bin/env python3
"""
🚀 MONSTER VALIDATOR by monsterdrak - WINDOWS + TXT READY (2026)
Real-time results + TXT output + Beginner friendly coder github.com/officialmonsterz
"""
import asyncio
import aiohttp
import aiosqlite
import csv
import json
import logging
import os
import re
import sys
import time
import random
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from urllib.parse import quote
import platform

# 🔥 WINDOWS FIX
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('monsterphone.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

@dataclass
class PhoneResult:
    number: str
    valid: bool
    active: Optional[bool] = None
    carrier: Optional[str] = None
    line_type: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    raw_data: Dict[str, Any] = None

class PhoneNormalizer:
    E164_REGEX = re.compile(r'^\+?[1-9]\d{1,14}$')
    
    @classmethod
    def normalize(cls, number: str) -> Optional[str]:
        number = re.sub(r'[^\d+]', '', number.strip())
        if number.startswith('00'):
            number = '+' + number[2:]
        elif not number.startswith('+'):
            number = '+' + number
        if cls.E164_REGEX.match(number):
            return number
        return None

class TwilioValidator:
    BASE_URL = "https://lookups.twilio.com/v2/PhoneNumbers"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.auth = aiohttp.BasicAuth(self.api_key, self.api_secret)
    
    async def validate(self, session: aiohttp.ClientSession, number: str) -> PhoneResult:
        url = f"{self.BASE_URL}/{quote(number)}"
        params = {"Type": "carrier"}
        try:
            async with session.get(url, auth=self.auth, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status >= 400:
                    return PhoneResult(number=number, valid=False)
                data = await resp.json()
                return PhoneResult(
                    number=number,
                    valid=data.get("valid", False),
                    active=data.get("reachable"),
                    carrier=data.get("carrier", {}).get("name"),
                    line_type=data.get("carrier", {}).get("type"),
                    country=data.get("country_code_iso2"),
                    region=data.get("national_format"),
                    raw_data=data
                )
        except Exception:
            return PhoneResult(number=number, valid=False)

class NumverifyValidator:
    BASE_URL = "http://apilayer.net/api/validate"
    
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
    
    async def validate(self, session: aiohttp.ClientSession, number: str) -> PhoneResult:
        params = {"access_key": self.api_key, "number": number, "format": "1"}
        try:
            async with session.get(self.BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                return PhoneResult(
                    number=number,
                    valid=data.get("valid", False),
                    carrier=data.get("carrier"),
                    line_type=data.get("line_type"),
                    country=data.get("country_name"),
                    region=data.get("location"),
                    timezone=data.get("location_timezone"),
                    raw_data=data
                )
        except Exception:
            return PhoneResult(number=number, valid=False)

class MonsterValidator:
    def __init__(self, db_path="monster.db"):
        self.db_path = Path(db_path)
        self.results: List[PhoneResult] = []
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY,
                    number TEXT UNIQUE,
                    valid INTEGER,
                    carrier TEXT,
                    line_type TEXT,
                    country TEXT,
                    processed_at TEXT
                )
            """)
            await db.commit()
    
    def load_numbers(self, file_path: str) -> List[str]:
        if not os.path.exists(file_path):
            return []
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and len(line.strip()) > 5]
    
    async def run_validation(self, config: Dict) -> List[PhoneResult]:
        numbers = self.load_numbers(config['input_file'])
        if not numbers:
            return []
        
        print(f"\n📱 Found {len(numbers)} numbers in numbers.txt")
        print("🔄 Validating each number LIVE...")
        print("=" * 60)
        
        provider = config['provider']
        api_key = config['api'][provider]['api_key']
        
        if provider == 'twilio':
            api_secret = config['api'][provider].get('api_secret', api_key)
            validator = TwilioValidator(api_key, api_secret)
        else:
            validator = NumverifyValidator(api_key)
        
        semaphore = asyncio.Semaphore(config['settings'].get('concurrency', 10))
        self.results = []
        valid_count = 0
        total_count = 0
        
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            for i, num in enumerate(numbers, 1):
                norm = PhoneNormalizer.normalize(num)
                if not norm:
                    result = PhoneResult(number=num, valid=False)
                    self.results.append(result)
                    print(f"[{i}/{len(numbers)}] ❌ {num} - INVALID FORMAT")
                    continue
                
                async def validate_single(n=norm):
                    async with semaphore:
                        result = await validator.validate(session, n)
                        return result
                
                result = await validate_single(norm)
                self.results.append(result)
                
                # 🔥 REAL-TIME RESULTS
                status = "✅ VALID" if result.valid else "❌ INVALID"
                carrier = result.carrier or "Unknown"
                line_type = result.line_type or "Unknown"
                print(f"[{i}/{len(numbers)}] {status} | {num} | {carrier} | {line_type}")
                
                if result.valid:
                    valid_count += 1
                total_count += 1
        
        # Mobile filter
        if config['settings'].get('mobile_only', False):
            original_count = len(self.results)
            self.results = [r for r in self.results if r.line_type and 'mobile' in r.line_type.lower()]
            print(f"\n📱 Mobile filter: {len(self.results)}/{original_count} kept")
        
        # Save DB
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            for r in self.results:
                await db.execute(
                    "INSERT OR REPLACE INTO results VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                    (r.number, int(r.valid), r.carrier, r.line_type, r.country, time.strftime('%Y-%m-%d %H:%M:%S'))
                )
            await db.commit()
        
        print(f"\n🎉 SUMMARY: {valid_count}/{total_count} VALID ({valid_count/total_count*100:.1f}%)")
        return self.results
    
    def export_results(self, output_file: str):
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # 🔥 TXT OUTPUT (EASIEST TO READ)
        txt_file = output_file.rsplit('.', 1)[0] + '.txt'
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("🚀 MONSTER VALIDATOR RESULTS\n")
            f.write("=" * 50 + "\n\n")
            valid_results = []
            invalid_results = []
            
            for r in self.results:
                line = f"{r.number} | {'✅ VALID' if r.valid else '❌ INVALID'}"
                if r.carrier:
                    line += f" | {r.carrier}"
                if r.line_type:
                    line += f" | {r.line_type}"
                if r.country:
                    line += f" | {r.country}"
                line += "\n"
                
                if r.valid:
                    valid_results.append(line)
                else:
                    invalid_results.append(line)
            
            f.write(f"✅ VALID NUMBERS ({len(valid_results)}):\n")
            f.writelines(valid_results)
            f.write("\n❌ INVALID NUMBERS:\n")
            f.writelines(invalid_results)
        
        print(f"📁 Results saved: {txt_file}")
        
        # JSON backup
        json_file = output_file
        data = [asdict(r) for r in self.results]
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"📊 JSON backup: {json_file}")

def load_config() -> Dict:
    default_config = {
        "input_file": "numbers.txt",
        "output_file": "results.json",
        "provider": "numverify",  # ✅ Changed to numverify (you have key)
        "api": {
            "twilio": {"api_key": "", "api_secret": ""},
            "numverify": {"api_key": "e4a5d65aa3e755f7ca25613cbe19abc7"}
        },
        "settings": {
            "concurrency": 10,  # Lower for stability
            "mobile_only": False  # ✅ Disabled mobile_only filter causing empty results
        }
    }
    
    config_path = Path("config.json")
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except:
            pass
    return default_config

def save_config(config: Dict):
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

def print_banner():
    print("\n" + "="*70)
    print("🚀 MONSTER VALIDATOR - REAL-TIME PHONE VALIDATION")
    print("📱 Numbers file: numbers.txt (confirmed)")
    print("="*70)

def confirm_numbers_file():
    if os.path.exists("numbers.txt"):
        count = len([l for l in open("numbers.txt") if l.strip()])
        print(f"✅ numbers.txt CONFIRMED! Found {count} numbers")
        return True
    print("❌ numbers.txt NOT FOUND!")
    print("💡 Create numbers.txt with phone numbers (one per line)")
    return False

def main_menu():
    print_banner()
    
    while True:
        try:
            config = load_config()
            
            print("\n📋 MENU:")
            print("1️⃣  🚀 VALIDATE numbers.txt (LIVE RESULTS)")
            print("2️⃣  📝 Edit Config")
            print("3️⃣  📱 Generate Test Numbers")
            print("4️⃣  📊 View Results")
            print("5️⃣  ❌ Exit")
            
            choice = input("\n➤ Choose: ").strip()
            
            if choice == '1':
                if confirm_numbers_file():
                    print("\n🔄 Starting LIVE validation...")
                    validator = MonsterValidator()
                    results = asyncio.run(validator.run_validation(config))
                    
                    if results:
                        validator.export_results(config['output_file'])
                        
                        valid_count = len([r for r in results if r.valid])
                        print(f"\n🎉 COMPLETE! {valid_count}/{len(results)} VALID")
                        print("📁 Check results.txt for full report!")
                    else:
                        print("❌ No results")
                input("\nPress ENTER...")
            
            elif choice == '2':
                config['provider'] = input("Provider (twilio/numverify) [numverify]: ").strip().lower() or 'numverify'
                if config['provider'] == 'numverify':
                    config['api']['numverify']['api_key'] = input("Numverify API Key: ").strip() or config['api']['numverify']['api_key']
                else:
                    config['api']['twilio']['api_key'] = input("Twilio SID: ").strip()
                    config['api']['twilio']['api_secret'] = input("Twilio Token: ").strip()
                config['settings']['mobile_only'] = input("Mobile only? (y/n): ").strip().lower() in ['y', 'yes']
                save_config(config)
                print("✅ Config saved!")
                input("\nPress ENTER...")
            
            elif choice == '3':
                count = int(input("How many test numbers? (10): ") or "10")
                countries = ['1', '44', '33', '49', '234']
                with open("numbers.txt", 'w') as f:
                    for _ in range(count):
                        country = random.choice(countries)
                        num = f"+{country}{random.randint(1000000000, 9999999999)}"
                        f.write(num + "\n")
                print(f"✅ Generated {count} test numbers in numbers.txt")
                input("\nPress ENTER...")
            
            elif choice == '4':
                if os.path.exists("results.txt"):
                    print("\n📋 RESULTS:")
                    with open("results.txt", 'r') as f:
                        print(f.read()[:1000])  # First 1000 chars
                else:
                    print("❌ No results.txt found")
                input("\nPress ENTER...")
            
            elif choice == '5':
                print("👋 Bye!")
                break
            
        except KeyboardInterrupt:
            print("\n👋 Cancelled")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main_menu()
