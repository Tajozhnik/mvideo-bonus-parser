import requests
import csv
import time
import json
import random
import logging
import sys
import base64
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    MY_BONUS: int = """СКОЛЬКО У ВАС БОНУСОВ"""
    # Снижаем порог чтобы увидеть ВСЕ распределение
    MIN_BONUS_PERCENT: float = 1.0
    MIN_PRICE: int = 100
    MAX_PRICE: int = 0
    DELAY_MIN: float = 1.0
    DELAY_MAX: float = 2.0
    PAGE_SIZE: int = 36
    MAX_PAGES_PER_CATEGORY: int = 100
    OUTPUT_FILE: str = "mvideo_bonus_all.csv"
    # Режим: "scan" — собрать статистику, "find" — искать топ
    MODE: str = "scan"


config = Config()

RAW_COOKIE = """КУКИСЫ"""

CATEGORIES = [
    {"id": "205",   "name": "Смартфоны"},
    {"id": "95",    "name": "Мобильные телефоны"},
    {"id": "4367",  "name": "Домашние телефоны"},
    {"id": "65",    "name": "Телевизоры"},
    {"id": "74",    "name": "Проекторы и экраны"},
    {"id": "358",   "name": "Smart TV приставки"},
    {"id": "4247",  "name": "Кронштейны для телевизоров"},
    {"id": "54",    "name": "Наушники"},
    {"id": "202",   "name": "Портативная акустика"},
    {"id": "192",   "name": "Hi-Fi акустика"},
    {"id": "2547",  "name": "Саундбары"},
    {"id": "212",   "name": "Домашние кинотеатры"},
    {"id": "236",   "name": "Микрофоны"},
    {"id": "118",   "name": "Ноутбуки"},
    {"id": "195",   "name": "Планшеты"},
    {"id": "101",   "name": "Мониторы"},
    {"id": "80",    "name": "Системные блоки"},
    {"id": "181",   "name": "Моноблоки"},
    {"id": "146",   "name": "МФУ"},
    {"id": "81",    "name": "Принтеры"},
    {"id": "82",    "name": "Сканеры"},
    {"id": "217",   "name": "Клавиатуры и комплекты"},
    {"id": "183",   "name": "Мыши"},
    {"id": "208",   "name": "Веб-камеры"},
    {"id": "5436",  "name": "SSD"},
    {"id": "5433",  "name": "Оперативная память"},
    {"id": "5429",  "name": "Видеокарты"},
    {"id": "5431",  "name": "Процессоры"},
    {"id": "5432",  "name": "Материнские платы"},
    {"id": "400",   "name": "Смарт-часы"},
    {"id": "403",   "name": "Фитнес-браслеты"},
    {"id": "36197", "name": "Смарт-кольца"},
    {"id": "5607",  "name": "Умные гаджеты"},
    {"id": "2207",  "name": "Очки виртуальной реальности"},
    {"id": "1944",  "name": "Внешние аккумуляторы"},
    {"id": "12",    "name": "Фотоаппараты"},
    {"id": "2288",  "name": "Экшн-камеры"},
    {"id": "42",    "name": "Аксессуары для фото и видеотехники"},
    {"id": "7710",  "name": "Товары для блогеров"},
    {"id": "29",    "name": "Приготовление кофе"},
    {"id": "155",   "name": "Кофемашины"},
    {"id": "36459", "name": "Капсульные кофемашины"},
    {"id": "157",   "name": "Кофеварки"},
    {"id": "145",   "name": "Кофемолки"},
    {"id": "94",    "name": "Микроволновки"},
    {"id": "159",   "name": "Холодильники и морозильные камеры"},
    {"id": "2427",  "name": "Стиральные и сушильные машины"},
    {"id": "89",    "name": "Стиральные машины"},
    {"id": "30550", "name": "Сушильные машины"},
    {"id": "2428",  "name": "Пылесосы и аксессуары"},
    {"id": "2438",  "name": "Пылесосы"},
    {"id": "36410", "name": "Роботы-пылесосы"},
    {"id": "11",    "name": "Климатическая техника"},
    {"id": "106",   "name": "Кондиционеры"},
    {"id": "124",   "name": "Увлажнители и очистители воздуха"},
    {"id": "125",   "name": "Обогреватели"},
    {"id": "55882", "name": "Игровые консоли и игры"},
    {"id": "57137", "name": "Игровые консоли"}
]


def create_session():
    s = requests.Session()
    cookie_str = RAW_COOKIE.strip().replace("\n", "").replace("\r", "")
    if not cookie_str or "ВСТАВЬТЕ" in cookie_str:
        logger.error("❌ Заполните RAW_COOKIE!")
        raise SystemExit(1)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "ru,en-US;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Origin": "https://www.mvideo.ru",
        "Referer": "https://www.mvideo.ru/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "Cookie": cookie_str,
    })
    return s


def delay(mul=1.0):
    time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX) * mul)


def safe_json(resp):
    if not resp or not resp.text:
        return None
    try:
        return resp.json()
    except:
        return None


def encode_filter_params(*filters):
    params = []
    for f in filters:
        params.extend(f)
    return base64.b64encode(json.dumps(params, ensure_ascii=False).encode()).decode()


def get_product_ids(session, category_id, offset=0, limit=36):
    url = "https://www.mvideo.ru/bff/products/v2/search"
    fp = encode_filter_params(("tolko-v-nalichii", "-12", "da"))
    params = {
        "categoryIds": category_id, "offset": offset, "limit": limit,
        "filterParams": fp, "doTranslit": "true", "context": "",
    }
    try:
        r = session.get(url, params=params, timeout=30)
        if r.status_code != 200:
            return [], 0
        d = safe_json(r)
        if not d or not d.get("success"):
            return [], 0
        body = d["body"]
        return [str(p) for p in body.get("products", [])], body.get("total", 0)
    except Exception as e:
        logger.error(f"search: {e}")
        return [], 0


@dataclass
class PriceInfo:
    product_id: str = ""
    base_price: float = 0
    base_promo_price: float = 0
    sale_price: float = 0
    bonus_write_off: float = 0
    bonus_percent: float = 0
    cashback: float = 0
    price_discount: float = 0


def get_prices_with_bonus(session, product_ids):
    if not product_ids:
        return {}
    url = "https://www.mvideo.ru/bff/products/prices"
    params = {
        "productIds": ",".join(product_ids),
        "addBonusRubles": "true",
        "isPromoApplied": "true",
    }
    try:
        r = session.get(url, params=params, timeout=30)
        if r.status_code != 200:
            return {}
        d = safe_json(r)
        if not d or not d.get("success"):
            return {}
        result = {}
        for item in d["body"].get("materialPrices", []):
            pid = str(item.get("productId", ""))
            price = item.get("price", {})
            base_price = price.get("basePrice", 0)
            base_promo_price = price.get("basePromoPrice", 0)
            sale_price = price.get("salePrice", 0)

            bonus_write_off = 0
            price_discount = 0
            for disc in price.get("discounts", []):
                dtype = disc.get("type", "")
                damount = disc.get("discount", 0)
                if dtype == "BONUS_RUBLES":
                    bonus_write_off = damount
                elif dtype in ("PRICE", "YOUR_PRICE"):
                    price_discount += damount

            bonus_percent = 0
            if base_promo_price > 0 and bonus_write_off > 0:
                bonus_percent = round((bonus_write_off / base_promo_price) * 100, 1)

            cb = item.get("bonusRubles", {}).get("total", 0)
            result[pid] = PriceInfo(
                product_id=pid, base_price=base_price,
                base_promo_price=base_promo_price, sale_price=sale_price,
                bonus_write_off=bonus_write_off, bonus_percent=bonus_percent,
                cashback=cb, price_discount=price_discount,
            )
        return result
    except Exception as e:
        logger.error(f"prices: {e}")
        return {}


@dataclass
class ProductDetail:
    product_id: str = ""
    name: str = ""
    url: str = ""
    brand: str = ""


def get_details(session, product_ids):
    if not product_ids:
        return {}
    url = "https://www.mvideo.ru/bff/product-details/list"
    body = {
        "productIds": product_ids,
        "mediaTypes": ["images"],
        "category": True, "status": True, "brand": True,
        "propertyTypes": ["KEY"],
        "propertiesConfig": {"propertiesPortionSize": 5},
    }
    try:
        r = session.post(url, json=body, timeout=30)
        if r.status_code != 200:
            return {}
        d = safe_json(r)
        if not d or not d.get("success"):
            return {}
        result = {}
        for p in d["body"].get("products", []):
            pid = str(p["productId"])
            nt = p.get("nameTranslit", "")
            result[pid] = ProductDetail(
                product_id=pid, name=p.get("name", pid),
                url=f"https://www.mvideo.ru/products/{nt}-{pid}" if nt else "",
                brand=p.get("brandName", ""),
            )
        return result
    except Exception as e:
        logger.error(f"details: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════
# ГЛОБАЛЬНАЯ СТАТИСТИКА
# ═══════════════════════════════════════════════════════════════
class BonusStats:
    """Собирает статистику по % бонусов по всем товарам."""

    def __init__(self):
        self.total_products = 0
        self.products_with_bonus = 0
        self.percent_distribution = defaultdict(int)  # % -> count
        self.top_products = []  # (percent, pid, name, price, bonus)
        self.max_percent = 0
        self.category_stats = {}  # cat_name -> {max_pct, avg_pct, count}

    def add(self, pid, name, category, price, bonus_amount, bonus_pct):
        self.total_products += 1
        if bonus_amount > 0:
            self.products_with_bonus += 1

            # Группировка по %
            bucket = int(bonus_pct)
            self.percent_distribution[bucket] += 1

            if bonus_pct > self.max_percent:
                self.max_percent = bonus_pct

            # Храним топ-100
            self.top_products.append((bonus_pct, pid, name, price, bonus_amount, category))
            self.top_products.sort(key=lambda x: -x[0])
            if len(self.top_products) > 100:
                self.top_products = self.top_products[:100]

            # По категориям
            if category not in self.category_stats:
                self.category_stats[category] = {
                    "max_pct": 0, "total_pct": 0, "count": 0
                }
            cs = self.category_stats[category]
            cs["count"] += 1
            cs["total_pct"] += bonus_pct
            if bonus_pct > cs["max_pct"]:
                cs["max_pct"] = bonus_pct

    def print_report(self):
        logger.info("\n" + "=" * 70)
        logger.info("📊 ПОЛНЫЙ ОТЧЁТ ПО БОНУСАМ М.ВИДЕО")
        logger.info("=" * 70)

        logger.info(f"\n  Всего товаров проверено:  {self.total_products}")
        logger.info(f"  С BONUS_RUBLES:           {self.products_with_bonus}")
        logger.info(f"  Максимальный %:           {self.max_percent}%")

        # Распределение
        logger.info(f"\n  📈 Распределение по % списания:")
        logger.info(f"  {'%':>5s}  {'Кол-во':>8s}  {'Гистограмма'}")
        logger.info(f"  {'─'*50}")

        for pct in sorted(self.percent_distribution.keys(), reverse=True):
            count = self.percent_distribution[pct]
            bar = "█" * min(count, 50)
            logger.info(f"  {pct:>4d}%  {count:>8d}  {bar}")

        # По категориям
        logger.info(f"\n  📁 По категориям:")
        logger.info(f"  {'Категория':<25s} {'Макс%':>6s} {'Средн%':>7s} {'Кол-во':>7s}")
        logger.info(f"  {'─'*50}")
        for cat in sorted(self.category_stats.keys()):
            cs = self.category_stats[cat]
            avg = cs["total_pct"] / cs["count"] if cs["count"] > 0 else 0
            logger.info(
                f"  {cat:<25s} {cs['max_pct']:>5.1f}% {avg:>6.1f}% {cs['count']:>7d}"
            )

        # Топ товары
        logger.info(f"\n  🏆 ТОП-50 товаров с максимальным % бонусов:")
        logger.info(f"  {'─'*70}")
        for i, (pct, pid, name, price, bonus, cat) in enumerate(self.top_products[:50], 1):
            my_use = min(bonus, config.MY_BONUS)
            logger.info(
                f"  {i:3d}. [{pct:>5.1f}%] {name[:45]}\n"
                f"       {cat} | {price:.0f}₽ −{my_use:.0f}бр → {price - my_use:.0f}₽"
            )

        logger.info("\n" + "=" * 70)


# ═══════════════════════════════════════════════════════════════
# РЕЗУЛЬТАТ
# ═══════════════════════════════════════════════════════════════
@dataclass
class Product:
    product_id: str = ""
    name: str = ""
    brand: str = ""
    category: str = ""
    url: str = ""
    base_price: float = 0
    price_before_bonus: float = 0
    sale_price: float = 0
    bonus_write_off: float = 0
    bonus_percent: float = 0
    my_bonus_use: float = 0
    my_final_price: float = 0
    cashback: float = 0


# ═══════════════════════════════════════════════════════════════
# ОБРАБОТКА
# ═══════════════════════════════════════════════════════════════
def process_batch(session, product_ids, cat_name, results, stats):
    if not product_ids:
        return 0, 0

    prices = get_prices_with_bonus(session, product_ids)
    if not prices:
        return 0, 0

    has_bonus = 0
    good_ids = []

    for pid in product_ids:
        pi = prices.get(pid)
        if not pi:
            continue

        if pi.bonus_write_off > 0:
            has_bonus += 1
            # Добавляем в статистику (имя пока пустое, заполним ниже)
            stats.add(pid, pid, cat_name, pi.base_promo_price,
                      pi.bonus_write_off, pi.bonus_percent)

        if pi.bonus_percent >= config.MIN_BONUS_PERCENT:
            good_ids.append(pid)

    # Получаем детали только для хороших товаров
    if good_ids:
        details = get_details(session, good_ids)
        delay(0.3)

        # Обновляем имена в статистике
        for pid in good_ids:
            pi = prices[pid]
            det = details.get(pid, ProductDetail(product_id=pid, name=f"Товар {pid}"))

            # Обновляем имя в top_products
            for j, (pct, tpid, tname, tprice, tbonus, tcat) in enumerate(stats.top_products):
                if tpid == pid and tname == pid:
                    stats.top_products[j] = (pct, tpid, det.name, tprice, tbonus, tcat)

            my_use = min(pi.bonus_write_off, config.MY_BONUS)
            my_final = pi.base_promo_price - my_use

            results.append(Product(
                product_id=pid, name=det.name, brand=det.brand,
                category=cat_name, url=det.url,
                base_price=pi.base_price,
                price_before_bonus=pi.base_promo_price,
                sale_price=pi.sale_price,
                bonus_write_off=pi.bonus_write_off,
                bonus_percent=pi.bonus_percent,
                my_bonus_use=my_use, my_final_price=my_final,
                cashback=pi.cashback,
            ))

            logger.info(
                f"  ✅ {det.name[:50]:50s} | "
                f"{pi.base_promo_price:>7.0f}₽ "
                f"−{pi.bonus_write_off:.0f}бр ({pi.bonus_percent}%) "
                f"→ {my_final:.0f}₽"
            )

    # Получаем имена для топа (если не получили выше)
    top_pids_without_name = [
        tpid for (_, tpid, tname, _, _, tcat) in stats.top_products
        if tname == tpid and tcat == cat_name and tpid in product_ids
    ]
    if top_pids_without_name:
        top_details = get_details(session, top_pids_without_name[:12])
        delay(0.3)
        for j, (pct, tpid, tname, tprice, tbonus, tcat) in enumerate(stats.top_products):
            if tpid in top_details:
                stats.top_products[j] = (
                    pct, tpid, top_details[tpid].name, tprice, tbonus, tcat
                )

    return len(good_ids), has_bonus


def process_category(session, category, results, stats):
    cat_id = category["id"]
    cat_name = category["name"]
    logger.info(f"\n📁 {cat_name} (ID: {cat_id})")

    offset = 0
    total = None
    page = 0
    found_total = 0
    bonus_total = 0

    while page < config.MAX_PAGES_PER_CATEGORY:
        pids, total_count = get_product_ids(session, cat_id, offset, config.PAGE_SIZE)
        if total is None:
            total = total_count
            logger.info(f"  Товаров в наличии: {total}")
        if not pids:
            break

        delay(0.3)
        found, has_bonus = process_batch(session, pids, cat_name, results, stats)
        found_total += found
        bonus_total += has_bonus
        delay(0.3)

        offset += config.PAGE_SIZE
        page += 1
        if offset >= total:
            break

        if page % 10 == 0:
            logger.info(f"  ... стр.{page}, {offset}/{total}")

    logger.info(f"  📊 С бонусами: {bonus_total}, подходящих: {found_total}")
    return found_total


def save_results(results):
    seen = set()
    unique = []
    for r in results:
        if r.product_id not in seen:
            seen.add(r.product_id)
            unique.append(r)
    unique.sort(key=lambda r: (-r.bonus_percent, -r.bonus_write_off))

    with open(config.OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "ID", "Название", "Бренд", "Категория",
            "Цена без скидок", "Цена до бонусов",
            "Бонусов списание", "% списания",
            "Мои бонусы", "Итого к оплате",
            "Кешбэк", "Ссылка",
        ])
        for r in unique:
            w.writerow([
                r.product_id, r.name, r.brand, r.category,
                int(r.base_price), int(r.price_before_bonus),
                int(r.bonus_write_off), f"{r.bonus_percent}%",
                int(r.my_bonus_use), int(r.my_final_price),
                int(r.cashback), r.url,
            ])

    logger.info(f"\n💾 {config.OUTPUT_FILE} ({len(unique)} товаров)")
    return unique


def save_full_stats(stats: BonusStats):
    """Сохраняет полную статистику в отдельный CSV."""
    fname = "mvideo_bonus_stats.csv"
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Место", "% бонусов", "ID", "Название", "Категория",
                     "Цена", "Бонусов", "Мои бонусы", "Итого"])
        for i, (pct, pid, name, price, bonus, cat) in enumerate(stats.top_products, 1):
            my_use = min(bonus, config.MY_BONUS)
            w.writerow([
                i, f"{pct}%", pid, name, cat,
                int(price), int(bonus), int(my_use), int(price - my_use),
            ])
    logger.info(f"💾 {fname} (ТОП-{len(stats.top_products)} товаров)")


def main():
    logger.info("=" * 60)
    logger.info("🔍 М.Видео Bonus Finder v12")
    logger.info("   Сканирование ВСЕХ товаров + статистика бонусов")
    logger.info("=" * 60)

    session = create_session()

    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        pid = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "400242809"

        prices = get_prices_with_bonus(session, [pid])
        if not prices or pid not in prices:
            logger.error("❌ Цены не получены")
            return
        pi = prices[pid]
        details = get_details(session, [pid])
        det = details.get(pid, ProductDetail(product_id=pid))

        logger.info(f"\n  {det.name}")
        logger.info(f"  Базовая:       {pi.base_price:>8.0f}₽")
        logger.info(f"  Скидка:        {pi.price_discount:>8.0f}₽")
        logger.info(f"  До бонусов:    {pi.base_promo_price:>8.0f}₽")
        logger.info(f"  БОНУС:         {pi.bonus_write_off:>8.0f}₽ ({pi.bonus_percent}%)")
        logger.info(f"  Итого:         {pi.sale_price:>8.0f}₽")
        logger.info(f"  Кешбэк:        {pi.cashback:>8.0f}₽")

        my_use = min(pi.bonus_write_off, config.MY_BONUS)
        logger.info(f"\n  Ваши {config.MY_BONUS} бонусов:")
        logger.info(f"  Спишется: {my_use:.0f}₽ → К оплате: {pi.base_promo_price - my_use:.0f}₽")
        logger.info(f"  {det.url}")
        return

    if "--test-listing" in sys.argv:
        idx = sys.argv.index("--test-listing")
        cid = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "205"

        pids, total = get_product_ids(session, cid, 0, 36)
        logger.info(f"Всего: {total}, получено: {len(pids)}")
        if not pids:
            return

        delay()
        prices = get_prices_with_bonus(session, pids)

        # Статистика по этой странице
        with_bonus = [(pid, prices[pid]) for pid in pids
                       if pid in prices and prices[pid].bonus_write_off > 0]
        with_bonus.sort(key=lambda x: -x[1].bonus_percent)

        logger.info(f"\nС BONUS_RUBLES: {len(with_bonus)}/{len(pids)}")
        logger.info(f"{'ID':>12s} {'Цена':>8s} {'Бонус':>7s} {'%':>6s}")
        logger.info(f"{'─'*40}")
        for pid, pi in with_bonus:
            logger.info(
                f"{pid:>12s} {pi.base_promo_price:>8.0f} "
                f"{pi.bonus_write_off:>7.0f} {pi.bonus_percent:>5.1f}%"
            )

        if with_bonus:
            max_pct = max(pi.bonus_percent for _, pi in with_bonus)
            min_pct = min(pi.bonus_percent for _, pi in with_bonus)
            avg_pct = sum(pi.bonus_percent for _, pi in with_bonus) / len(with_bonus)
            logger.info(f"\nМин: {min_pct}% | Средн: {avg_pct:.1f}% | Макс: {max_pct}%")
        return

    # ═════════════════════════════════
    # ПОЛНОЕ СКАНИРОВАНИЕ
    # ═════════════════════════════════
    logger.info(f"\n⚙ Бонусы: {config.MY_BONUS:,}₽ | Мин %: {config.MIN_BONUS_PERCENT}%")

    # Верификация
    prices = get_prices_with_bonus(session, ["400242809"])
    if not prices or prices["400242809"].bonus_write_off == 0:
        logger.error("❌ BONUS_RUBLES не приходит. Обновите cookies.")
        return
    pi = prices["400242809"]
    logger.info(f"✅ Верификация: Xiaomi Redmi 13C бонус={pi.bonus_write_off}₽ ({pi.bonus_percent}%)")
    delay()

    stats = BonusStats()
    results = []

    for i, cat in enumerate(CATEGORIES, 1):
        logger.info(f"\n[{i}/{len(CATEGORIES)}] {'─' * 40}")
        try:
            process_category(session, cat, results, stats)
        except KeyboardInterrupt:
            logger.info("\n⏹ Прервано.")
            break
        except Exception as e:
            logger.error(f"  ❌ {cat['name']}: {e}")

        # Промежуточный отчёт каждые 5 категорий
        if i % 5 == 0:
            logger.info(f"\n  📊 Промежуточно: проверено {stats.total_products}, "
                        f"с бонусами {stats.products_with_bonus}, "
                        f"макс% {stats.max_percent}%")

    # ПОЛНЫЙ ОТЧЁТ
    stats.print_report()

    # Сохраняем
    if results:
        save_results(results)

    save_full_stats(stats)

    # Вывод для пользователя
    logger.info("\n" + "=" * 70)
    if stats.max_percent >= 45:
        logger.info(f"🔥 Найдены товары с {stats.max_percent}% бонусов!")
    elif stats.max_percent >= 20:
        logger.info(f"👍 Максимальный % бонусов: {stats.max_percent}%")
        logger.info(f"   Товаров с 50% бонусов НЕ найдено.")
        logger.info(f"   Возможно сейчас нет такой акции.")
    else:
        logger.info(f"😐 Максимальный % бонусов: {stats.max_percent}%")
        logger.info(f"   Стандартное списание ≈6% на большинство товаров.")

    logger.info(f"\n💡 Чтобы максимально использовать {config.MY_BONUS} бонусов:")
    logger.info(f"   Смотрите файл mvideo_bonus_stats.csv — там ТОП-100 товаров.")
    logger.info(f"   Лучшая стратегия: купить несколько недорогих товаров")
    logger.info(f"   с бонусами на каждый, чтобы суммарно списать все {config.MY_BONUS}₽.")

    # Подсчёт оптимальной комбинации
    if stats.top_products:
        logger.info(f"\n🧮 Оптимальная комбинация для списания {config.MY_BONUS} бонусов:")
        remaining = config.MY_BONUS
        combo = []
        used_total = 0
        for pct, pid, name, price, bonus, cat in stats.top_products:
            if remaining <= 0:
                break
            use = min(bonus, remaining)
            combo.append((name, price, use, pct))
            remaining -= use
            used_total += use
            if remaining <= 0:
                break

        for i, (name, price, use, pct) in enumerate(combo, 1):
            logger.info(f"  {i}. {name[:50]}")
            logger.info(f"     {price:.0f}₽ −{use:.0f}бр ({pct}%) → {price - use:.0f}₽")

        logger.info(f"\n  Итого списано: {used_total}₽ из {config.MY_BONUS}₽")
        logger.info(f"  Остаток: {config.MY_BONUS - used_total}₽")


if __name__ == "__main__":
    main()
