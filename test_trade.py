"""
测试下单 - 强制开一个小额测试单
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.exchange.okx_client import OKXClient
import yaml

# 加载配置
with open('config/settings.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
    okx_config = config.get("exchange", {}).get("okx", {})

# 创建客户端
client = OKXClient(
    api_key=okx_config.get('api_key'),
    api_secret=okx_config.get('api_secret'),
    passphrase=okx_config.get('passphrase'),
    testnet=True
)

symbol = "BTC/USDT:USDT"

print("=" * 60)
print("OKX模拟盘测试下单")
print("=" * 60)

# 1. 设置杠杆
print("\n1. 设置10x杠杆...")
try:
    result = client.set_leverage(symbol, 10)
    print(f"   结果: {result}")
except Exception as e:
    print(f"   警告: {e}")

# 2. 获取当前价格
print("\n2. 获取当前价格...")
ticker = client.exchange.fetch_ticker(symbol)
current_price = ticker['last']
print(f"   BTC当前价格: {current_price}")

# 3. 开市价多单 0.01 BTC（约700 USDT）
print("\n3. 开市价多单 0.01 BTC...")
try:
    order = client.create_order(
        symbol=symbol,
        order_type='market',
        side='buy',
        amount=0.01
    )
    print(f"   订单ID: {order.get('id', 'failed')}")
    print(f"   状态: {order.get('status', 'unknown')}")
    print(f"   价格: {order.get('average', order.get('price', 'pending'))}")
    print(f"   数量: {order.get('filled', order.get('amount', 0))}")
    print(f"   手续费: {order.get('fee', {}).get('cost', 0)} {order.get('fee', {}).get('currency', 'USDT')}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 4. 查询持仓
print("\n4. 查询当前持仓...")
try:
    positions = client.get_positions(symbol)
    print(f"   持仓数量: {len(positions)}")
    for pos in positions:
        print(f"   - {pos.symbol}: {pos.side} {pos.size} BTC @ {pos.entry_price}")
        print(f"     未实现盈亏: {pos.unrealized_pnl:.2f} USDT")
        print(f"     杠杆: {pos.leverage}x")
except Exception as e:
    print(f"   错误: {e}")

# 5. 查询账户余额
print("\n5. 查询账户余额...")
try:
    account = client.get_account_info()
    print(f"   USDT余额: {account.balance_usdt:.2f}")
    print(f"   可用余额: {account.available_balance:.2f}")
    print(f"   已用保证金: {account.margin_used:.2f}")
except Exception as e:
    print(f"   错误: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
