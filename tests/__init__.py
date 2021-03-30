import sys
from pathlib import Path

comp_path: Path = Path(__file__).parent / "../custom_components"
sys.path.append(str(comp_path.resolve()))
