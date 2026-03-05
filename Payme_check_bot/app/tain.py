import sys
from pathlib import Path

# 3 papka yuqoriga chiqish
sys.path.append(str(Path(__file__).parent.parent.parent))

from config import *

print("Tain fayli ishga tushdi...")
print("Bot token:", BOT_TOKEN)
print("Bot username:", BOT_USERNAME)