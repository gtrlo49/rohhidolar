"""Registry of bank sources. A failing bank never affects the others."""

from bolidolar.banks.common import BankSpec
from bolidolar.banks.json_banks import BEC, BGA, BMSC, FIE
from bolidolar.banks.text_banks import BCP, BISA, BNB, BUN

BANKS: tuple[BankSpec, ...] = (BNB, BCP, BISA, FIE, BEC, BUN, BGA, BMSC)

__all__ = ["BANKS", "BankSpec"]
