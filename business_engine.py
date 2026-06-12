# =========================
# BUSINESS ENGINE v2.0
# AI 商業規則核心（不可改動邏輯層）
# =========================

class BusinessEngine:

    # =========================
    # 📅 週薪制規則
    # =========================
    WEEKLY_RULES = {
        "settlement_start": "週一 13:00 (TW)",
        "settlement_end": "下週一 12:59 (TW)",
        "payout_day": "兩周後的周一",
        "currency": "USD"
    }

    def get_weekly_rule(self):
        return self.WEEKLY_RULES

    # =========================
    # 🧠 X39 基礎規格（不可變）
    # =========================
    X39_PRICE = 99.95
    X39_QDV = 77
    X39_BV = 43

    # =========================
    # 💰 PC / PC+ 收益模型
    # =========================
    def pc_weekly_income(self, pc_count: int):
        return pc_count * 20  # USD / week

    # =========================
    # 📊 QDV / BV
    # =========================
    def calc_qdv(self, pc_count: int):
        return pc_count * self.X39_QDV

    def calc_bv(self, pc_count: int):
        return pc_count * self.X39_BV

    # =========================
    # 📊 客戶介紹金（QDV 獎金）
    # =========================
    def referral_bonus(self, total_qdv: int):

        if total_qdv >= 1200:
            return total_qdv * 0.20

        if total_qdv >= 600:
            return total_qdv * 0.10

        if total_qdv >= 300:
            return total_qdv * 0.05

        return 0

    # =========================
    # ⚖️ 雙向獎金規則
    # =========================
    def dual_bonus(self, level: str, small_side_bv: int):

        if level in ["S1", "S2"]:
            return 0  # ❌ 禁止

        if level == "S3":
            return small_side_bv * 0.05

        if level == "D":
            return small_side_bv * 0.07

        return 0

    # =========================
    # 🧭 經理判定邏輯
    # =========================
    def is_two_star_manager(self, personal_qdv: int):
        return personal_qdv >= 1500  # 約 20 PC+

    def is_director(self, team_qdv: int):
        return team_qdv >= 5000

    # =========================
    # 📦 快速試算工具（給 AI 用）
    # =========================
    def quick_preview(self, pc_count: int):

        return {
            "pc_count": pc_count,
            "weekly_income": self.pc_weekly_income(pc_count),
            "qdv": self.calc_qdv(pc_count),
            "bv": self.calc_bv(pc_count)
        }
