"""
OKX模拟盘连接测试
"""

import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.exchange.okx_client import OKXClient


def test_okx_demo():
    """测试OKX模拟盘连接"""

    print("=" * 60)
    print("OKX模拟盘连接测试")
    print("=" * 60)

    # 获取API凭证（优先从环境变量，其次从配置文件）
    import yaml
    config_path = "config/settings.yaml"
    config_api_key = ""
    config_api_secret = ""
    config_passphrase = ""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            okx_config = config.get("exchange", {}).get("okx", {})
            config_api_key = okx_config.get("api_key", "")
            config_api_secret = okx_config.get("api_secret", "")
            config_passphrase = okx_config.get("passphrase", "")
    except Exception:
        pass

    api_key = os.environ.get("OKX_API_KEY", config_api_key)
    api_secret = os.environ.get("OKX_API_SECRET", config_api_secret)
    passphrase = os.environ.get("OKX_PASSPHRASE", config_passphrase)

    # 检查API Key
    print("\n1. API凭证检查:")
    if not api_key:
        print("   [X] 未设置 OKX_API_KEY")
        print("\n   请设置环境变量或修改config/settings.yaml:")
        print("   set OKX_API_KEY=your_api_key")
        print("   set OKX_API_SECRET=your_api_secret")
        print("   set OKX_PASSPHRASE=your_passphrase")
        print("\n   获取API Key步骤:")
        print("   1. 访问 https://www.okx.com/cn/demo-v2")
        print("   2. 登录OKX账号（或注册新账号）")
        print("   3. 进入 [交易] -> [模拟交易]")
        print("   4. 点击右上角头像 -> [API] -> [创建API Key]")
        print("   5. 复制 API Key, Secret Key, Passphrase")
        return False

    print(f"   [OK] API Key: {api_key[:10]}...")
    print(f"   [OK] Secret: {api_secret[:10]}..." if api_secret else "   [X] Secret未设置")
    print(f"   [OK] Passphrase: {passphrase[:3]}..." if passphrase else "   [X] Passphrase未设置")

    if not api_secret or not passphrase:
        return False

    # 创建客户端
    print("\n2. 初始化OKX模拟盘客户端:")
    client = OKXClient(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        testnet=True  # 使用模拟盘
    )
    print("   [OK] 客户端初始化成功")

    # 测试连接 - 获取账户信息
    print("\n3. 测试获取账户信息:")
    try:
        account = client.get_account_info()
        print(f"   [OK] 连接成功!")
        print(f"   USDT余额: {account.balance_usdt:.2f}")
        print(f"   可用余额: {account.available_balance:.2f}")
        print(f"   已用保证金: {account.margin_used:.2f}")
    except Exception as e:
        print(f"   [X] 获取账户信息失败: {e}")
        return False

    # 测试获取持仓
    print("\n4. 测试获取持仓:")
    try:
        positions = client.get_positions()
        print(f"   [OK] 获取持仓成功")
        print(f"   当前持仓数量: {len(positions)}")
        for pos in positions:
            print(f"     - {pos.symbol}: {pos.side} {pos.size} @ {pos.entry_price}")
    except Exception as e:
        print(f"   [X] 获取持仓失败: {e}")

    # 测试获取行情
    print("\n5. 测试获取行情数据:")
    try:
        # 获取K线
        ohlcv = client.fetch_ohlcv("BTC/USDT:USDT", "1h", 5)
        print(f"   [OK] 获取K线成功: {len(ohlcv)} 条")

        # 获取订单簿
        orderbook = client.fetch_order_book("BTC/USDT:USDT", 5)
        if orderbook:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            print(f"   [OK] 获取订单簿成功")
            print(f"      买一: {bids[0][0] if bids else 'N/A'}")
            print(f"      卖一: {asks[0][0] if asks else 'N/A'}")

        # 获取资金费率
        funding = client.fetch_funding_rate("BTC/USDT:USDT")
        if funding:
            print(f"   [OK] 获取资金费率成功: {funding.get('fundingRate', 'N/A')}")

    except Exception as e:
        print(f"   [X] 获取行情失败: {e}")

    print("\n" + "=" * 60)
    print("[OK] OKX模拟盘测试完成")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_okx_demo()
    sys.exit(0 if success else 1)
