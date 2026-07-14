"""
抽象画像生成器接口

从 profile_config.yaml 读取概率配置驱动画像生成，
替代 user_profile.py 中硬编码的概率判断。
"""

import random
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from faker import Faker

from synth_engine.core.config import ProfileConfigModel
from synth_engine.core.utils import weighted_choice

_csv_cache: Dict[str, pd.DataFrame] = {}


def _load_csv_cached(path: str) -> pd.DataFrame:
    if path not in _csv_cache:
        _csv_cache[path] = pd.read_csv(path)
    return _csv_cache[path]


class ConfigDrivenProfileGenerator:
    """
    配置驱动的用户画像生成器。

    所有概率分布从 profile_config.yaml 读取，而非硬编码在代码中。
    """

    def __init__(self, config, seed: Optional[int] = None,
                 df_fund: Optional[pd.DataFrame] = None,
                 df_wealth: Optional[pd.DataFrame] = None):
        """
        Args:
            config: 可以是 dict 或 ProfileConfigModel（Pydantic）
            seed: 随机种子
            df_fund: 基金产品 DataFrame（外部传入，优先级高于 CSV 配置）
            df_wealth: 理财产品 DataFrame（外部传入，优先级高于 CSV 配置）
        """
        self.config = config
        if seed is not None:
            random.seed(seed)
        self.faker = Faker("zh_CN")
        # Convert to plain dict for .get() access
        if isinstance(config, dict):
            self._cfg = config
        else:
            self._cfg = config.model_dump() if hasattr(config, "model_dump") else dict(config)
        # 外部传入的 DataFrame 优先级最高，否则从 CSV 加载
        self.df_fund = df_fund
        self.df_wealth = df_wealth
        self._init_data_pools()
        self._load_product_pools()

    def _init_data_pools(self):
        """从配置初始化数据池"""
        pools = self._cfg.get("data_pools") or {}
        self.cities = pools.get("cities", [
            "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆",
            "天津", "苏州", "郑州", "长沙", "青岛", "大连", "厦门", "宁波", "无锡", "福州",
        ])
        self.occupations = pools.get("occupations", [
            "IT工程师", "医生", "教师", "公务员", "金融从业者", "自由职业者",
            "企业主", "学生", "退休人员", "销售", "会计", "律师", "设计师",
            "建筑工程师", "市场营销", "人力资源", "研究员", "技术员", "护士", "媒体人",
        ])
        self.branches = pools.get("branches", [
            "北京分行营业部", "上海分行营业部", "广州分行营业部", "深圳分行营业部",
            "杭州分行营业部", "成都分行营业部", "武汉分行营业部", "南京分行营业部",
            "西安分行营业部", "重庆分行营业部", "天津分行营业部", "苏州分行营业部",
        ])
        self.banks = pools.get("banks", [
            "工商银行", "建设银行", "农业银行", "中国银行", "招商银行",
            "交通银行", "邮储银行", "中信银行", "浦发银行", "民生银行",
            "光大银行", "华夏银行", "平安银行", "兴业银行", "广发银行",
        ])
        self.payee_relations = pools.get("payee_relations", [
            "亲友", "商户", "工资", "还款", "投资", "其他",
        ])

    def _load_product_pools(self):
        """从配置加载基金/理财产品池 CSV"""
        pp = self._cfg.get("product_pools") or {}

        # 基金产品池
        if self.df_fund is None:
            fund_csv = pp.get("fund_csv")
            if fund_csv:
                try:
                    # 相对于模板目录解析路径
                    cfg_dir = Path(self._cfg.get("__config_dir__", "."))
                    csv_path = (cfg_dir / fund_csv).resolve()
                    if csv_path.exists():
                        self.df_fund = _load_csv_cached(str(csv_path))
                except Exception:
                    pass
            if self.df_fund is None or self.df_fund.empty:
                self.df_fund = self._default_fund_pool()

        # 理财产品池
        if self.df_wealth is None:
            wealth_csv = pp.get("wealth_csv")
            if wealth_csv:
                try:
                    cfg_dir = Path(self._cfg.get("__config_dir__", "."))
                    csv_path = (cfg_dir / wealth_csv).resolve()
                    if csv_path.exists():
                        self.df_wealth = _load_csv_cached(str(csv_path))
                except Exception:
                    pass
            if self.df_wealth is None or self.df_wealth.empty:
                self.df_wealth = self._default_wealth_pool()

    @staticmethod
    def _default_fund_pool() -> pd.DataFrame:
        """内置默认基金产品池（兜底用）"""
        return pd.DataFrame([
            {"code": "000001", "fund_name": "华夏成长混合", "fund_type": "混合型-灵活"},
            {"code": "000003", "fund_name": "中海可转债债券A", "fund_type": "债券型-混合二级"},
            {"code": "000006", "fund_name": "西部利得量化成长混合A", "fund_type": "混合型-偏股"},
            {"code": "000008", "fund_name": "嘉实中证500ETF联接A", "fund_type": "指数型-股票"},
            {"code": "000009", "fund_name": "易方达天天理财货币A", "fund_type": "货币型-普通货币"},
            {"code": "000011", "fund_name": "华夏大盘精选混合A", "fund_type": "混合型-偏股"},
            {"code": "110011", "fund_name": "易方达中小盘混合", "fund_type": "混合型-灵活"},
            {"code": "161725", "fund_name": "招商中证白酒指数", "fund_type": "指数型-股票"},
            {"code": "260108", "fund_name": "景顺长城新兴成长混合", "fund_type": "混合型-偏股"},
            {"code": "320007", "fund_name": "诺安成长混合", "fund_type": "混合型-偏股"},
        ])

    @staticmethod
    def _default_wealth_pool() -> pd.DataFrame:
        """内置默认理财产品池（兜底用）"""
        return pd.DataFrame([
            {"product_name": "工银理财·如意人生鑫添益纯债对冲策略", "product_yield": "1.00%-2.00%"},
            {"product_name": "工银理财·鑫得利固收封闭理财产品", "product_yield": "1.50%-1.70%"},
            {"product_name": "工银理财·稳益固收类封闭理财产品", "product_yield": "1.30%"},
            {"product_name": "工银理财·核心优选目标止盈策略固收封闭", "product_yield": "1.90%-2.10%"},
            {"product_name": "招银理财招睿颐养丰润三个月封闭1号增强型固收", "product_yield": "4.33%"},
            {"product_name": "招银理财招睿智远两年封闭1号增强型固收", "product_yield": "2.91%"},
            {"product_name": "建信理财乾元-龙盈固收封闭", "product_yield": "3.20%-3.50%"},
            {"product_name": "中银理财稳富固收类封闭式", "product_yield": "2.80%-3.20%"},
        ])

    # ========== 配置读取辅助 ==========

    def _get_basic(self):
        return self._cfg.get("basic_attributes") or {}

    def _get_debit(self):
        return self._cfg.get("debit_card") or {}

    def _get_credit(self):
        return self._cfg.get("credit_card") or {}

    def _get_payees_cfg(self):
        return self._cfg.get("payees") or {}

    def _get_holdings_prob(self):
        return self._cfg.get("holdings_probability") or {}

    def _get_holdings_count(self):
        return self._cfg.get("holdings_count") or {}

    def _get_deposits_cfg(self):
        return self._cfg.get("deposits") or {}

    def _get_loans_cfg(self):
        return self._cfg.get("loans") or {}

    def _get_service_prob(self):
        return self._cfg.get("service_probability") or {}

    def _get_security_cfg(self):
        return self._cfg.get("security") or {}

    def _get_benefits_cfg(self):
        return self._cfg.get("benefits") or {}

    def _get_digital_rmb_cfg(self):
        return self._cfg.get("digital_rmb") or {}

    def _get_salary_cfg(self):
        return self._cfg.get("salary") or {}

    def _get_payment_agreements_cfg(self):
        return self._cfg.get("payment_agreements") or {}

    def _get_transactions_cfg(self):
        return self._cfg.get("transactions") or {}

    def _get_investment_profile(self):
        return self._cfg.get("investment_profile") or {}

    def _get_behavior_cfg(self):
        return self._cfg.get("behavior") or {}

    def _get_insurance_products(self):
        return self._cfg.get("insurance_products") or []

    def _get_bond_products(self):
        return self._cfg.get("bond_products") or []

    def _get_precious_metals(self):
        return self._cfg.get("precious_metals") or []

    def _get_balance_distribution(self):
        return self._cfg.get("balance_distribution") or {}

    def _prob(self, key: str, default: float = 0.5) -> bool:
        """从 holdings_probability 或 service_probability 中获取概率并判断"""
        hp = self._get_holdings_prob()
        if key in hp:
            return random.random() < hp[key]
        sp = self._get_service_prob()
        if key in sp:
            return random.random() < sp[key]
        return random.random() < default

    def _log_randint(self, min_val: int, max_val: int) -> int:
        if min_val <= 0 or max_val <= 0 or min_val >= max_val:
            return random.randint(max(1, min_val), max(1, max_val))
        return int(math.exp(random.uniform(math.log(min_val), math.log(max_val))))

    def _biased_balance_randint(self, card_level: str) -> int:
        """从 balance_distribution 配置读取余额分布"""
        dist = self._get_balance_distribution().get(card_level, {})
        if not dist:
            return self._log_randint(100, 10000)

        rand = random.random()
        cumulative = 0.0
        for range_key, prob in dist.items():
            cumulative += prob
            if rand < cumulative:
                return self._parse_range(range_key)
        last_key = list(dist.keys())[-1]
        return self._parse_range(last_key)

    @staticmethod
    def _parse_range(range_key: str) -> int:
        range_key = range_key.strip()
        if "-" in range_key:
            parts = range_key.split("-")
            return random.randint(int(parts[0]), int(parts[1]))
        elif range_key.startswith("<"):
            return random.randint(0, int(range_key[1:]) - 1)
        elif range_key.startswith(">"):
            return random.randint(int(range_key[1:]) + 1, int(range_key[1:]) * 5)
        return 1000

    # ========== 基本信息 ==========

    def generate_basic_info(self) -> Dict[str, Any]:
        ba = self._get_basic()
        age_range = ba.get("age_range", [18, 70])
        age = random.randint(age_range[0], age_range[1])
        birth_year = datetime.now().year - age
        birth_date = datetime(birth_year, random.randint(1, 12), random.randint(1, 28))
        id_prefix = self.faker.ssn()[:6]
        id_birth = birth_date.strftime("%Y%m%d")
        id_suffix = "".join([str(random.randint(0, 9)) for _ in range(4)])
        id_number = id_prefix + id_birth + id_suffix

        phone_prefixes = ba.get("phone_prefixes", ["138", "139", "136"])
        phone_prefix = random.choice(phone_prefixes)
        phone_number = phone_prefix + "".join([str(random.randint(0, 9)) for _ in range(8)])

        city = random.choice(self.cities)

        education_weights = ba.get("education_weights", {"高中及以下": 1, "大专": 1, "本科": 2, "硕士": 1, "博士": 0.5})
        marital_weights = ba.get("marital_weights", {"未婚": 1, "已婚": 1, "离异": 0.3})
        customer_tier_weights = ba.get("customer_tier_weights", {"普通": 0.6, "优质": 0.3, "高净值": 0.1})

        risk_range = ba.get("risk_tolerance_range", [1, 5])

        is_same_city = random.random() < ba.get("is_same_city_prob", 0.7)

        return {
            "name": self.faker.name(),
            "gender": random.choice(["男", "女"]),
            "age": age,
            "birth_date": birth_date.strftime("%Y-%m-%d"),
            "id_number": id_number,
            "phone_number": phone_number,
            "occupation": random.choice(self.occupations),
            "education": weighted_choice(list(education_weights.keys()), list(education_weights.values())),
            "marital_status": weighted_choice(list(marital_weights.keys()), list(marital_weights.values())),
            "has_children": random.random() < ba.get("has_children_prob", 0.5),
            "city": city,
            "address": self.faker.address(),
            "card_issuing_city": city if is_same_city else random.choice(self.cities),
            "is_same_city": is_same_city,
            "risk_tolerance": random.randint(risk_range[0], risk_range[1]),
            "email": f"{phone_number}@example.com",
            "customer_tier": weighted_choice(list(customer_tier_weights.keys()), list(customer_tier_weights.values())),
        }

    # ========== 借记卡 ==========

    def generate_debit_cards(self, count: int, age: int) -> List[Dict[str, Any]]:
        """生成借记卡列表

        根据央行规定：同一家银行只能有 1 个 I类户，II类/III类户最多各 5 个。
        第一张卡固定为 I类户（主账户），后续卡片从 II类户/III类户中抽取。
        """
        dc = self._get_debit()
        cards = []
        for i in range(count):
            if i == 0:
                # 第一张卡固定为 I类户（央行规定一人一行只能有一个I类户）
                account_type = "I类户"
                card_level = self._pick_card_level(dc)
                balance = self._biased_balance_randint(card_level)
                age_factor_min = dc.get("age_factor_min", 0.3)
                age_factor_max = dc.get("age_factor_max", 1.0)
                age_factor = age_factor_min + (age / 100) * (age_factor_max - age_factor_min)
                balance = int(balance * age_factor)
            else:
                # 后续卡片只能从 II类户/III类户中选择
                account_type_weights = dc.get("account_type_weights", {
                    "II类户": 0.8, "III类户": 0.2,
                })
                account_type = weighted_choice(list(account_type_weights.keys()), list(account_type_weights.values()))
                card_level = "普卡"
                balance = self._biased_balance_randint(card_level)
            status_weights = dc.get("status_weights", {"正常": 0.67, "挂失": 0.17, "冻结": 0.17})
            status = weighted_choice(list(status_weights.keys()), list(status_weights.values()))
            avail_ratio = dc.get("available_balance_ratio", [0.9, 1.0])
            cards.append({
                "card_no": self.faker.credit_card_number(),
                "card_type": "借记卡",
                "card_level": card_level,
                "account_type": account_type,
                "branch": random.choice(self.branches),
                "balance": balance,
                "available_balance": int(balance * random.uniform(avail_ratio[0], avail_ratio[1])),
                "status": status,
                "open_date": (datetime.now() - timedelta(days=random.randint(30, max(30, age * 365)))).strftime("%Y-%m-%d"),
                "is_primary": i == 0,
                "annual_fee": 10 if card_level == "普卡" else (20 if card_level == "金卡" else 0),
                "is_annual_fee_waived": random.random() < dc.get("annual_fee_waived_prob", 0.7),
            })
        return cards

    def _pick_card_level(self, dc: Dict) -> str:
        """根据配置抽取卡片级别"""
        levels = list(dc.get("level_weights", {"普卡": 0.6, "金卡": 0.25, "白金卡": 0.12, "钻石卡": 0.03}).keys())
        weights = list(dc.get("level_weights", {}).values())
        return random.choices(levels, weights=weights)[0]

    # ========== 信用卡 ==========

    def generate_credit_cards(self, count: int, age: int, occupation: str) -> List[Dict[str, Any]]:
        cc = self._get_credit()
        cards = []
        products = cc.get("credit_products", [])
        if not products:
            products = [
                {"name": "工银标准信用卡", "type": "金卡", "base_limit": 20000},
            ]

        high_limit_occupations = cc.get("high_limit_occupations", ["企业主", "金融从业者", "IT工程师"])
        high_limit_age = cc.get("high_limit_age", 35)
        high_limit_mult = cc.get("high_limit_multiplier", [2, 5])
        mid_limit_age = cc.get("mid_limit_age", 30)
        mid_limit_mult = cc.get("mid_limit_multiplier", [1.2, 2])
        used_limit_ratio = cc.get("used_limit_ratio", [0.1, 0.8])
        bill_days = [int(x) for x in cc.get("bill_days", [1, 5, 10, 15, 20, 25])]
        auto_repay_prob = cc.get("auto_repayment_prob", 0.75)
        has_points_prob = cc.get("has_points_prob", 0.7)
        points_range = cc.get("points_range", [0, 50000])
        status_weights = cc.get("status_weights", {"正常": 0.67, "未激活": 0.17, "已冻结": 0.17})

        for _ in range(count):
            card_product = random.choice(products)
            base_limit = card_product.get("base_limit", 20000)

            if age > high_limit_age and occupation in high_limit_occupations:
                limit = int(base_limit * random.uniform(high_limit_mult[0], high_limit_mult[1]))
            elif age > mid_limit_age:
                limit = int(base_limit * random.uniform(mid_limit_mult[0], mid_limit_mult[1]))
            else:
                limit = base_limit

            used_limit = int(limit * random.uniform(used_limit_ratio[0], used_limit_ratio[1]))
            available_limit = limit - used_limit
            bill_day = random.choice(bill_days)
            due_day = (bill_day + 20) % 30 or 30
            bill_amount = int(used_limit * random.uniform(0.5, 1.0))
            min_payment = int(bill_amount * 0.1)
            points = random.randint(points_range[0], points_range[1]) if random.random() < has_points_prob else 0
            status = weighted_choice(list(status_weights.keys()), list(status_weights.values()))

            cards.append({
                "card_no": self.faker.credit_card_number(),
                "card_name": card_product["name"],
                "card_type": card_product["type"],
                "limit": limit,
                "used_limit": used_limit,
                "available_limit": available_limit,
                "bill_day": bill_day,
                "due_day": due_day,
                "current_bill_amount": bill_amount,
                "min_payment": min_payment,
                "points": points,
                "status": status,
                "open_date": (datetime.now() - timedelta(days=random.randint(30, max(30, min(age - 18, 20) * 365)))).strftime("%Y-%m-%d"),
                "expire_date": (datetime.now() + timedelta(days=random.randint(365, 5 * 365))).strftime("%Y-%m"),
                "auto_repayment": random.random() < auto_repay_prob,
                "repayment_account": None,
            })
        return cards

    # ========== 收款人 ==========

    def generate_payees(self, count: int) -> List[Dict[str, Any]]:
        pc = self._get_payees_cfg()
        payees = []
        merchant_pool = pc.get("merchant_pool", ["京东", "淘宝", "拼多多", "美团", "滴滴", "支付宝", "微信"])
        repayment_names = pc.get("repayment_names", ["房贷还款", "车贷还款", "信用卡还款"])

        for i in range(count):
            relation = random.choice(self.payee_relations)
            if relation == "亲友":
                name = self.faker.name()
            elif relation == "商户":
                name = random.choice(merchant_pool)
            elif relation == "工资":
                name = random.choice(["工资卡", "备用金", "奖金"])
            elif relation == "还款":
                name = random.choice(repayment_names)
            else:
                name = self.faker.name()

            payees.append({
                "id": f"PAYEE_{i + 1:03d}",
                "name": name,
                "account_no": self.faker.credit_card_number(),
                "bank_name": random.choice(self.banks),
                "relation": relation,
                "is_frequent": random.random() < pc.get("is_frequent_prob", 0.5),
                "add_date": (datetime.now() - timedelta(days=random.randint(1, 1000))).strftime("%Y-%m-%d"),
                "phone": "".join([str(random.randint(0, 9)) for _ in range(11)]) if random.random() < pc.get("has_phone_prob", 0.5) else None,
            })
        return payees

    # ========== 基金/理财持仓（从 CSV 产品池读取） ==========

    def generate_fund_holdings(self, risk_tolerance: int) -> List[Dict[str, Any]]:
        hc = self._get_holdings_count()
        invest = self._get_investment_profile()
        risk_map = {1: "保守", 2: "稳健", 3: "平衡", 4: "成长", 5: "积极"}
        risk_appetite = risk_map.get(risk_tolerance, "平衡")
        prefs = invest.get("preferences", {}).get(risk_appetite, {})
        fund_types = prefs.get("fund_types", ["货币基金", "债券基金"])

        if not self._prob("has_fund"):
            return []

        num_funds = random.randint(1, min(hc.get("fund_max_per_risk", 5), risk_tolerance + 1))
        df = self.df_fund
        if df is None or df.empty:
            return []

        # 从 CSV 产品池随机抽取
        selected = df.sample(min(num_funds, len(df)))

        holdings = []
        for _, fund in selected.iterrows():
            shares = round(random.uniform(100, 10000), 2)
            cost_price = round(random.uniform(0.8, 2.0), 4)
            nav = round(cost_price * random.uniform(0.9, 1.3), 4)
            market_value = round(shares * nav, 2)
            cost_amount = round(shares * cost_price, 2)
            profit_loss = round(market_value - cost_amount, 2)
            profit_loss_rate = round((profit_loss / cost_amount) * 100, 2)
            holdings.append({
                "fund_code": str(fund.get("code", f"{random.randint(100000, 999999)}")),
                "fund_name": fund.get("fund_name", "未知基金"),
                "fund_type": fund.get("fund_type", random.choice(fund_types)),
                "shares": shares,
                "cost_price": cost_price,
                "nav": nav,
                "cost_amount": cost_amount,
                "market_value": market_value,
                "profit_loss": profit_loss,
                "profit_loss_rate": profit_loss_rate,
                "buy_date": (datetime.now() - timedelta(days=random.randint(30, 1000))).strftime("%Y-%m-%d"),
            })
        return holdings

    def generate_wealth_holdings(self, risk_tolerance: int) -> List[Dict[str, Any]]:
        hc = self._get_holdings_count()
        invest = self._get_investment_profile()
        risk_map = {1: "保守", 2: "稳健", 3: "平衡", 4: "成长", 5: "积极"}
        risk_appetite = risk_map.get(risk_tolerance, "平衡")
        prefs = invest.get("preferences", {}).get(risk_appetite, {})
        wealth_types = prefs.get("wealth_type", ["固定收益类"])

        if not self._prob("has_wealth"):
            return []

        num_products = random.randint(1, min(hc.get("wealth_max_per_risk", 4), risk_tolerance + 1))
        df = self.df_wealth
        if df is None or df.empty:
            return []

        # 从 CSV 产品池随机抽取
        selected = df.sample(min(num_products, len(df)))

        holdings = []
        for _, product in selected.iterrows():
            amount = self._log_randint(10000, 500000)
            term_days = random.choice([30, 90, 180, 365, 730])
            holdings.append({
                "product_code": f"WP{random.randint(100000, 999999)}",
                "product_name": product.get("product_name", "未知理财"),
                "product_type": random.choice(wealth_types),
                "amount": amount,
                "expected_annual_return": round(random.uniform(0.025, 0.05), 4),
                "buy_date": (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d"),
                "maturity_date": (datetime.now() + timedelta(days=term_days)).strftime("%Y-%m-%d"),
                "remaining_days": term_days,
                "accumulated_profit": round(amount * random.uniform(0, 0.03), 2),
                "is_redeemable": random.random() > 0.5,
                "auto_reinvest": random.choice([True, False]),
            })
        return holdings

    # ========== 存款 ==========

    def generate_deposit_holdings(self) -> List[Dict[str, Any]]:
        dp = self._get_deposits_cfg()
        holdings = []

        if random.random() < dp.get("has_large_deposit_prob", 0.7):
            num_large = random.randint(dp.get("large_deposit_count", [1, 3])[0], dp.get("large_deposit_count", [1, 3])[1])
            for _ in range(num_large):
                term = random.choice(dp.get("large_deposit_terms", [12, 24, 36]))
                amount = self._log_randint(dp.get("large_deposit_range", [200000, 1000000])[0],
                                           dp.get("large_deposit_range", [200000, 1000000])[1])
                rate_range = dp.get("large_deposit_rate_range", [0.0225, 0.035])
                holdings.append({
                    "deposit_type": "大额存单",
                    "amount": amount,
                    "term_months": term,
                    "annual_rate": round(random.uniform(rate_range[0], rate_range[1]), 4),
                    "deposit_date": (datetime.now() - timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d"),
                    "maturity_date": (datetime.now() + timedelta(days=term * 30)).strftime("%Y-%m-%d"),
                    "is_transferable": True,
                    "early_withdrawal_rate": 0.003,
                })

        if random.random() < dp.get("has_fixed_deposit_prob", 0.8):
            num_fixed = random.randint(dp.get("fixed_deposit_count", [1, 3])[0], dp.get("fixed_deposit_count", [1, 3])[1])
            for _ in range(num_fixed):
                term = random.choice(dp.get("fixed_deposit_terms", [3, 6, 12, 24, 36, 60]))
                amount = self._log_randint(dp.get("fixed_deposit_range", [10000, 500000])[0],
                                           dp.get("fixed_deposit_range", [10000, 500000])[1])
                rate_range = dp.get("fixed_deposit_rate_range", [0.015, 0.03])
                holdings.append({
                    "deposit_type": "定期存款",
                    "amount": amount,
                    "term_months": term,
                    "annual_rate": round(random.uniform(rate_range[0], rate_range[1]), 4),
                    "deposit_date": (datetime.now() - timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d"),
                    "maturity_date": (datetime.now() + timedelta(days=term * 30)).strftime("%Y-%m-%d"),
                    "auto_rollover": random.random() < dp.get("auto_rollover_prob", 0.67),
                })
        return holdings

    # ========== 保险 ==========

    def generate_insurance_holdings(self) -> List[Dict[str, Any]]:
        hc = self._get_holdings_count()
        if not self._prob("has_insurance"):
            return []

        products = self._get_insurance_products()
        if not products:
            products = [
                {"code": "PA001", "name": "工银安盛人寿鑫如意", "type": "寿险", "category": "终身寿险"},
                {"code": "PA002", "name": "工银安盛人寿御立方", "type": "重疾险", "category": "健康险"},
                {"code": "PA003", "name": "工银安盛人寿鑫丰益", "type": "年金险", "category": "年金险"},
                {"code": "PA004", "name": "工银安盛综合意外险", "type": "意外险", "category": "意外险"},
                {"code": "PA005", "name": "工银安盛百万医疗险", "type": "医疗险", "category": "健康险"},
            ]

        ic = hc.get("insurance_count", [1, 3])
        holdings = []
        for _ in range(random.randint(ic[0], ic[1])):
            product = random.choice(products)
            coverage = self._log_randint(100000, 1000000)
            premium = int(coverage * random.uniform(0.001, 0.01))
            term_years = random.choice([1, 5, 10, 20, 30, 99])
            holdings.append({
                "policy_no": f"POL{random.randint(100000000, 999999999)}",
                "product_code": product["code"],
                "product_name": product["name"],
                "insurance_type": product["type"],
                "category": product["category"],
                "coverage": coverage,
                "premium": premium,
                "premium_frequency": random.choice(["年缴", "月缴", "趸缴"]),
                "start_date": (datetime.now() - timedelta(days=random.randint(30, 1000))).strftime("%Y-%m-%d"),
                "end_date": (datetime.now() + timedelta(days=term_years * 365)).strftime("%Y-%m-%d") if term_years < 99 else "终身",
                "status": random.choice(["生效中", "生效中", "生效中", "宽限期", "已失效"]),
                "beneficiary": random.choice(["法定", "指定"]),
                "cash_value": int(premium * random.uniform(0.5, 5)) if product["type"] in ["寿险", "年金险"] else 0,
            })
        return holdings

    # ========== 国债 ==========

    def generate_bond_holdings(self) -> List[Dict[str, Any]]:
        hc = self._get_holdings_count()
        if not self._prob("has_bond"):
            return []

        products = self._get_bond_products()
        if not products:
            products = [
                {"code": "240001", "name": "2024年记账式附息(一期)国债", "type": "记账式国债"},
                {"code": "240002", "name": "2024年记账式附息(二期)国债", "type": "记账式国债"},
            ]

        bc = hc.get("bond_count", [1, 2])
        holdings = []
        for _ in range(random.randint(bc[0], bc[1])):
            product = random.choice(products)
            amount = self._log_randint(10000, 200000)
            holdings.append({
                "bond_code": product["code"],
                "bond_name": product["name"],
                "bond_type": product["type"],
                "amount": amount,
                "annual_rate": round(random.uniform(0.025, 0.035), 4),
                "buy_date": (datetime.now() - timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d"),
                "maturity_date": (datetime.now() + timedelta(days=random.randint(365, 10 * 365))).strftime("%Y-%m-%d"),
                "interest_payment": random.choice(["按年付息", "到期付息"]),
            })
        return holdings

    # ========== 贵金属 ==========

    def generate_precious_metals_holdings(self) -> List[Dict[str, Any]]:
        hc = self._get_holdings_count()
        if not self._prob("has_metals"):
            return []

        metals = self._get_precious_metals()
        if not metals:
            metals = [
                {"code": "AU9999", "name": "账户黄金", "type": "账户贵金属", "unit": "克"},
                {"code": "AG9999", "name": "账户白银", "type": "账户贵金属", "unit": "克"},
            ]

        mc = hc.get("metals_count", [1, 3])
        selected = random.sample(metals, min(random.randint(mc[0], mc[1]), len(metals)))
        holdings = []
        for metal in selected:
            quantity = round(random.uniform(1, 100), 2)
            if "黄金" in metal["name"] or "金" in metal["name"]:
                avg_cost = round(random.uniform(300, 500), 2)
            else:
                avg_cost = round(random.uniform(3, 8), 2)
            current_price = round(avg_cost * random.uniform(0.9, 1.2), 2)
            market_value = round(quantity * current_price, 2)
            cost_value = round(quantity * avg_cost, 2)
            holdings.append({
                "code": metal["code"],
                "name": metal["name"],
                "type": metal["type"],
                "unit": metal["unit"],
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "cost_value": cost_value,
                "market_value": market_value,
                "profit_loss": round(market_value - cost_value, 2),
                "buy_date": (datetime.now() - timedelta(days=random.randint(30, 500))).strftime("%Y-%m-%d"),
            })
        return holdings

    # ========== 贷款 ==========

    def generate_loans(self, age: int) -> List[Dict[str, Any]]:
        lc = self._get_loans_cfg()
        if not self._prob("has_loan"):
            return []

        loan_types = lc.get("loan_types", [])
        if not loan_types:
            loan_types = [
                {"type": "信用贷款", "min_amount": 10000, "max_amount": 300000, "min_term": 6, "max_term": 60},
                {"type": "购房贷款", "min_amount": 200000, "max_amount": 5000000, "min_term": 60, "max_term": 360},
            ]

        max_loans = lc.get("loan_max_by_age", 3)
        num_loans = random.randint(1, max(1, min(max_loans, age // 20)))
        repayment_methods = lc.get("repayment_methods", ["等额本息", "等额本金", "先息后本"])

        loans = []
        for _ in range(num_loans):
            loan_type_info = random.choice(loan_types)
            amount = self._log_randint(loan_type_info["min_amount"], loan_type_info["max_amount"])
            term_months = random.choice(range(loan_type_info["min_term"], loan_type_info["max_term"] + 1, 12))

            rate_ranges = lc.get("rate_ranges", {})
            lt = loan_type_info["type"]
            if lt in rate_ranges:
                rate = round(random.uniform(rate_ranges[lt][0], rate_ranges[lt][1]), 4)
            elif lt == "购房贷款":
                rate = round(random.uniform(0.035, 0.045), 4)
            elif lt == "信用贷款":
                rate = round(random.uniform(0.04, 0.08), 4)
            else:
                rate = round(random.uniform(0.035, 0.06), 4)

            monthly_rate = rate / 12
            if monthly_rate > 0:
                monthly_payment = int(amount * monthly_rate * (1 + monthly_rate) ** term_months /
                                     ((1 + monthly_rate) ** term_months - 1))
            else:
                monthly_payment = amount // term_months

            paid_months = random.randint(0, max(0, term_months - 1))
            remaining_months = term_months - paid_months
            remaining_principal = int(amount * (1 - paid_months / term_months) * random.uniform(0.95, 1.05))

            loans.append({
                "loan_id": f"LOAN_{random.randint(10000000, 99999999)}",
                "loan_type": lt,
                "amount": amount,
                "term_months": term_months,
                "annual_rate": rate,
                "monthly_payment": monthly_payment,
                "remaining_months": remaining_months,
                "remaining_principal": remaining_principal,
                "start_date": (datetime.now() - timedelta(days=paid_months * 30)).strftime("%Y-%m-%d"),
                "end_date": (datetime.now() + timedelta(days=remaining_months * 30)).strftime("%Y-%m-%d"),
                "repayment_method": random.choice(repayment_methods),
                "status": "正常还款" if random.random() > lc.get("overdue_prob", 0.1) else "逾期",
                "is_mortgage": lt == "购房贷款",
                "tax_deductible": lt == "购房贷款" and random.random() < lc.get("is_mortgage_tax_deductible_prob", 0.5),
            })
        return loans

    # ========== 安全介质 ==========

    def generate_security_media(self) -> Dict[str, Any]:
        sc = self._get_security_cfg()
        has_udun = random.random() < sc.get("has_udun_prob", 0.5)

        media = {
            "has_udun": has_udun,
            "udun_info": None,
            "auth_methods": ["密码"],
            "default_auth": "短信验证码",
        }

        if has_udun:
            udun_status_weights = sc.get("udun_status_weights", {"正常": 0.75, "即将到期": 0.25})
            media["udun_info"] = {
                "serial_no": "".join([str(random.randint(0, 9)) for _ in range(10)]),
                "brand": random.choice(sc.get("udun_brands", ["飞天诚信", "天地融", "华大"])),
                "status": weighted_choice(list(udun_status_weights.keys()), list(udun_status_weights.values())),
                "expire_date": (datetime.now() + timedelta(days=random.randint(30, 5 * 365))).strftime("%Y-%m-%d"),
                "single_limit": self._log_randint(50000, 1000000),
                "daily_limit": self._log_randint(100000, 5000000),
            }
            media["auth_methods"].append("U盾")
            media["default_auth"] = "U盾"

        if random.random() < sc.get("has_fingerprint_prob", 0.7):
            media["auth_methods"].append("指纹")
        if random.random() < sc.get("has_face_auth_prob", 0.5):
            media["auth_methods"].append("刷脸")

        acct_lock = sc.get("account_lock", {})
        return media, {
            "night_lock": random.random() < acct_lock.get("night_lock_prob", 0.3),
            "overseas_lock": random.random() < acct_lock.get("overseas_lock_prob", 0.2),
            "online_pay_lock": random.random() < acct_lock.get("online_pay_lock_prob", 0.1),
        }

    # ========== 转账限额 ==========

    def generate_transfer_limits(self, card_level: str, has_udun: bool) -> Dict[str, Any]:
        if has_udun:
            single_limit = self._log_randint(500000, 5000000)
            daily_limit = single_limit * 5
        elif card_level in ["白金卡", "钻石卡"]:
            single_limit = self._log_randint(100000, 500000)
            daily_limit = single_limit * 3
        else:
            single_limit = self._log_randint(50000, 100000)
            daily_limit = single_limit * 2

        return {
            "single_limit": single_limit,
            "daily_limit": daily_limit,
            "monthly_limit": daily_limit * 30,
        }

    # ========== 权益 ==========

    def generate_benefits(self) -> Dict[str, Any]:
        bc = self._get_benefits_cfg()
        return {
            "i_dou_balance": random.randint(bc.get("i_dou_range", [0, 10000])[0], bc.get("i_dou_range", [0, 10000])[1]) if random.random() < bc.get("has_i_dou_prob", 0.7) else 0,
            "i_dou_expiring_soon": random.randint(bc.get("i_dou_expiring_range", [0, 500])[0], bc.get("i_dou_expiring_range", [0, 500])[1]),
            "coupons": random.randint(bc.get("coupons_range", [0, 10])[0], bc.get("coupons_range", [0, 10])[1]),
            "star_level": random.choice(bc.get("star_levels", ["一星", "二星", "三星", "四星", "五星", "六星", "七星"])),
            "star_points": random.randint(bc.get("star_points_range", [0, 100000])[0], bc.get("star_points_range", [0, 100000])[1]),
            "green_energy": random.randint(bc.get("green_energy_range", [0, 5000])[0], bc.get("green_energy_range", [0, 5000])[1]),
        }

    # ========== 民生服务 ==========

    def generate_livelihood_info(self) -> Dict[str, Any]:
        sp = self._get_service_prob()
        return {
            "has_social_security": random.random() < sp.get("has_social_security", 0.8),
            "has_medical_insurance": random.random() < sp.get("has_medical_insurance", 0.9),
            "has_housing_fund": random.random() < sp.get("has_housing_fund", 0.7),
            "has_personal_pension": random.random() < sp.get("has_personal_pension", 0.4),
            "pension_balance": self._log_randint(1000, 50000) if random.random() < sp.get("has_personal_pension", 0.4) else 0,
            "housing_fund_balance": self._log_randint(10000, 500000) if random.random() < sp.get("has_housing_fund", 0.7) else 0,
        }

    # ========== 支付代扣 ==========

    def generate_payment_agreements(self) -> List[Dict[str, Any]]:
        pa = self._get_payment_agreements_cfg()
        if random.random() >= pa.get("has_prob", 0.7):
            return []

        num_agreements = random.randint(pa.get("count_range", [1, 4])[0], pa.get("count_range", [1, 4])[1])
        utility_types = pa.get("utility_types", [])
        if not utility_types:
            utility_types = [
                {"type": "水费", "provider": "自来水公司"},
                {"type": "电费", "provider": "国家电网"},
                {"type": "燃气费", "provider": "燃气集团"},
                {"type": "话费", "provider_pool": ["中国移动", "中国联通", "中国电信"]},
            ]

        selected = random.sample(utility_types, min(num_agreements, len(utility_types)))
        limit_options = pa.get("limit_options", [500, 1000, 2000, 5000])

        agreements = []
        for item in selected:
            # 话费代扣从运营商池中随机选一个（每人只有一个运营商）
            if item.get("provider_pool"):
                provider = random.choice(item["provider_pool"])
            else:
                provider = item.get("provider", "")
            agreements.append({
                "agreement_id": f"AGR_{random.randint(100000, 999999)}",
                "type": item["type"],
                "provider": provider,
                "account_no": "".join([str(random.randint(0, 9)) for _ in range(8)]),
                "limit_per_time": random.choice(limit_options),
                "status": "已暂停" if random.random() < pa.get("paused_prob", 0.25) else "生效中",
                "sign_date": (datetime.now() - timedelta(days=random.randint(30, 1000))).strftime("%Y-%m-%d"),
            })
        return agreements

    # ========== 数字人民币 ==========

    def generate_digital_rmb_wallet(self) -> Optional[Dict[str, Any]]:
        dr = self._get_digital_rmb_cfg()
        wallet_type_weights = dr.get("wallet_type_weights", {"一类钱包": 0.1, "二类钱包": 0.3, "三类钱包": 0.4, "四类钱包": 0.2})
        wallet_types = list(wallet_type_weights.keys())
        weights = list(wallet_type_weights.values())
        wallet_type = random.choices(wallet_types, weights=weights)[0] if wallet_types else "二类钱包"

        balance_limits = {"一类钱包": 10000000, "二类钱包": 500000, "三类钱包": 20000, "四类钱包": 10000}
        max_balance = balance_limits.get(wallet_type, 500000)
        status_weights = dr.get("status_weights", {"正常": 0.75, "已停用": 0.25})

        return {
            "wallet_id": f"DM{random.randint(10000000000, 99999999999)}",
            "wallet_type": wallet_type,
            "balance": self._log_randint(0, min(10000, max_balance)),
            "balance_limit": max_balance,
            "status": weighted_choice(list(status_weights.keys()), list(status_weights.values())),
            "open_date": (datetime.now() - timedelta(days=random.randint(30, 500))).strftime("%Y-%m-%d"),
            "auto_recharge": random.random() < dr.get("auto_recharge_prob", 0.5),
        }

    # ========== 薪资信息 ==========

    def generate_salary_info(self, occupation: str) -> Optional[Dict[str, Any]]:
        sc = self._get_salary_cfg()
        excluded = sc.get("excluded_occupations", ["企业主", "自由职业者"])
        if occupation in excluded:
            return None

        salary_ranges = sc.get("salary_ranges", {})
        min_sal, max_sal = salary_ranges.get(occupation, salary_ranges.get("默认", [5000, 20000]))
        monthly_salary = self._log_randint(int(min_sal), int(max_sal))

        return {
            "has_salary_card": random.random() < sc.get("has_salary_card_prob", 0.8),
            "monthly_salary": monthly_salary,
            "company_name": self.faker.company() if random.random() < sc.get("has_company_prob", 0.7) else None,
            "salary_payment_day": random.choice(sc.get("payment_days", [5, 10, 15, 20, 25])),
            "last_salary_amount": monthly_salary,
            "last_salary_date": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
        }

    # ========== 交易记录 ==========

    def generate_transaction_history(self) -> List[Dict[str, Any]]:
        tc = self._get_transactions_cfg()
        count = random.randint(tc.get("count_range", [5, 20])[0], tc.get("count_range", [5, 20])[1])
        transaction_types = tc.get("types", ["转账", "消费", "缴费", "理财购买", "工资", "还款", "退款"])
        amount_range = tc.get("amount_range", [10, 50000])
        days_back = tc.get("days_back", [0, 30])

        transactions = []
        for _ in range(count):
            trans_type = random.choice(transaction_types)
            amount = self._log_randint(amount_range[0], amount_range[1])
            transactions.append({
                "trans_id": f"TXN{random.randint(100000000000, 999999999999)}",
                "type": trans_type,
                "amount": amount if trans_type in ["工资", "退款"] else -amount,
                "currency": "CNY",
                "counterparty": self.faker.name() if trans_type == "转账" else random.choice(["京东", "淘宝", "美团", "超市"]),
                "trans_time": (datetime.now() - timedelta(days=random.randint(days_back[0], days_back[1]), hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S"),
                "status": "成功",
                "remark": "",
            })
        transactions.sort(key=lambda x: x["trans_time"], reverse=True)
        return transactions

    # ========== 投资偏好 ==========

    def generate_investment_profile(self, risk_tolerance: int, age: int) -> Dict[str, Any]:
        invest = self._get_investment_profile()
        risk_mapping = invest.get("risk_mapping", {1: "保守", 2: "稳健", 3: "平衡", 4: "成长", 5: "积极"})
        risk_appetite = risk_mapping.get(risk_tolerance, "平衡")
        prefs = invest.get("preferences", {}).get(risk_appetite, {})

        fund_types = prefs.get("fund_types", ["货币基金", "债券基金"])
        wealth_types = prefs.get("wealth_type", ["固定收益类"])
        holding_period = prefs.get("holding_period", [12, 36])

        return {
            "risk_appetite": risk_appetite,
            "investment_experience": random.randint(0, max(0, age - 18)),
            "holding_period": random.randint(holding_period[0], holding_period[1]) if isinstance(holding_period, list) else holding_period,
            "investment_frequency": random.choice(["每周", "每月", "每季度", "不定期"]),
            "product_preferences": {
                "fund_types": random.sample(fund_types, k=min(len(fund_types), random.randint(1, len(fund_types)))),
                "wealth_product_types": random.sample(wealth_types, k=min(len(wealth_types), random.randint(1, len(wealth_types)))),
                "preferred_investment_channels": random.sample(["手机银行", "网上银行", "线下网点"], k=random.randint(1, 2)),
            },
        }

    # ========== 行为特征 ==========

    def generate_behavior(self, age: int) -> Dict[str, Any]:
        bh = self._get_behavior_cfg()
        app_version = bh.get("app_version", {})
        if age > 55:
            app_ver = random.choice(app_version.get(">55", ["标准版", "创新版", "幸福生活版"]))
        else:
            app_ver = random.choice(app_version.get("default", ["标准版", "创新版"]))

        login_freq = random.choice(bh.get("login_frequency", ["每日", "每周数次", "每月数次"]))
        channel_pool = bh.get("channel_pool", ["手机银行", "网上银行", "ATM", "柜台"])
        channel_count = bh.get("channel_count", [1, 3])
        menu_pool = bh.get("frequent_menu_pool", ["查余额", "转账汇款", "理财", "信用卡还款", "基金", "缴费"])
        menu_count = bh.get("frequent_menu_count", [3, 5])

        return {
            "app_version": app_ver,
            "login_frequency": login_freq,
            "preferred_channels": random.sample(channel_pool, k=random.randint(channel_count[0], channel_count[1])),
            "frequent_menus": random.sample(menu_pool, k=random.randint(menu_count[0], menu_count[1])),
        }

    # ========== 完整画像 ==========

    def generate_user_profile(
        self,
        user_id: Optional[str] = None,
        df_fund: Optional[pd.DataFrame] = None,
        df_wealth: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """生成完整的用户画像"""
        if not user_id:
            user_id = f"USER_{random.randint(100000, 999999)}"

        basic_info = self.generate_basic_info()
        age = basic_info["age"]
        occupation = basic_info["occupation"]
        risk_tolerance = basic_info["risk_tolerance"]

        # 借记卡数量
        dc = self._get_debit()
        debit_cfg = dc.get("count", {})
        if random.random() < debit_cfg.get("single_prob", 0.55):
            debit_count = 1
        else:
            debit_count = random.randint(2, debit_cfg.get("multi_max", 4))

        debit_cards = self.generate_debit_cards(debit_count, age)

        # 信用卡
        credit_cards = []
        cc = self._get_credit()
        if random.random() < cc.get("has_probability", 0.7):
            age_credit_count = cc.get("age_credit_count", {"<25": [1, 2], "25-40": [1, 4], ">40": [1, 3]})
            if age < 25:
                cr = age_credit_count.get("<25", [1, 2])
            elif age <= 40:
                cr = age_credit_count.get("25-40", [1, 4])
            else:
                cr = age_credit_count.get(">40", [1, 3])
            credit_count = random.randint(cr[0], cr[1])
            credit_cards = self.generate_credit_cards(credit_count, age, occupation)

        # 收款人
        payees = []
        pc = self._get_payees_cfg()
        if random.random() < pc.get("has_prob", 0.7):
            cr = pc.get("count_range", [3, 8])
            payees = self.generate_payees(random.randint(cr[0], cr[1]))

        # 各持仓
        fund_holdings = self.generate_fund_holdings(risk_tolerance)
        wealth_holdings = self.generate_wealth_holdings(risk_tolerance)
        deposit_holdings = self.generate_deposit_holdings()
        insurance_holdings = self.generate_insurance_holdings()
        bond_holdings = self.generate_bond_holdings()
        metals_holdings = self.generate_precious_metals_holdings()
        loans = self.generate_loans(age)

        # 安全
        security_media, account_lock = self.generate_security_media()
        primary_card_level = debit_cards[0]["card_level"] if debit_cards else "普卡"
        transfer_limits = self.generate_transfer_limits(primary_card_level, security_media["has_udun"])

        # 权益 & 民生
        benefits = self.generate_benefits()
        livelihood = self.generate_livelihood_info()

        # 支付代扣 & 数字人民币
        payment_agreements = self.generate_payment_agreements()
        digital_rmb = self.generate_digital_rmb_wallet()

        # 薪资 & 交易
        salary_info = self.generate_salary_info(occupation)
        transactions = self.generate_transaction_history()

        # 投资偏好 & 行为
        investment_profile = self.generate_investment_profile(risk_tolerance, age)
        behavior = self.generate_behavior(age)

        # 计算总资产和负债
        total_assets = sum(c["balance"] for c in debit_cards)
        total_assets += sum(c["available_limit"] for c in credit_cards)
        total_assets += sum(f["market_value"] for f in fund_holdings)
        total_assets += sum(w["amount"] for w in wealth_holdings)
        total_assets += sum(d["amount"] for d in deposit_holdings)
        total_assets += sum(b["amount"] for b in bond_holdings)
        total_assets += sum(m["market_value"] for m in metals_holdings)

        total_liability = sum(l["remaining_principal"] for l in loans)
        total_liability += sum(c["used_limit"] for c in credit_cards)

        return {
            "user_id": user_id,
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "basic_info": basic_info,
            "accounts": {
                "debit_cards": debit_cards,
                "credit_cards": credit_cards,
                "total_accounts": len(debit_cards) + len(credit_cards),
            },
            "payees": {
                "count": len(payees),
                "list": payees,
            },
            "investments": {
                "fund": {
                    "has_holdings": len(fund_holdings) > 0,
                    "holdings": fund_holdings,
                    "total_market_value": sum(f["market_value"] for f in fund_holdings),
                    "total_profit_loss": sum(f["profit_loss"] for f in fund_holdings),
                },
                "wealth_management": {
                    "has_holdings": len(wealth_holdings) > 0,
                    "holdings": wealth_holdings,
                    "total_amount": sum(w["amount"] for w in wealth_holdings),
                },
                "deposits": {
                    "has_holdings": len(deposit_holdings) > 0,
                    "holdings": deposit_holdings,
                    "total_amount": sum(d["amount"] for d in deposit_holdings),
                },
                "bonds": {
                    "has_holdings": len(bond_holdings) > 0,
                    "holdings": bond_holdings,
                    "total_amount": sum(b["amount"] for b in bond_holdings),
                },
                "precious_metals": {
                    "has_holdings": len(metals_holdings) > 0,
                    "holdings": metals_holdings,
                    "total_market_value": sum(m["market_value"] for m in metals_holdings),
                },
                "insurance": {
                    "has_holdings": len(insurance_holdings) > 0,
                    "policies": insurance_holdings,
                    "total_coverage": sum(p["coverage"] for p in insurance_holdings),
                    "annual_premium": sum(p["premium"] for p in insurance_holdings),
                },
            },
            "loans": {
                "has_loan": len(loans) > 0,
                "list": loans,
                "total_remaining": sum(l["remaining_principal"] for l in loans),
                "monthly_payment": sum(l["monthly_payment"] for l in loans),
            },
            "security": {
                "media": security_media,
                "limits": transfer_limits,
                "account_lock": account_lock,
            },
            "benefits": benefits,
            "livelihood": livelihood,
            "payment_agreements": payment_agreements,
            "digital_rmb": digital_rmb,
            "salary": salary_info,
            "investment_profile": investment_profile,
            "asset_summary": {
                "total_assets": total_assets,
                "total_liability": total_liability,
                "net_assets": total_assets - total_liability,
                "debt_ratio": round(total_liability / max(total_assets, 1), 4),
            },
            "recent_transactions": transactions,
            "behavior": behavior,
        }
