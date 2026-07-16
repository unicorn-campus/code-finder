"""프로젝트 루트를 sys.path에 추가해 `import kg`가 동작하도록 함."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
