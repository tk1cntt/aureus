import asyncio
from nautilus_trader.live.node import TradingNode
from config import get_node_config

async def main():
    config = get_node_config()
    node = TradingNode(config=config)
    print("Nautilus Node starting...")
    # Setup venues, instruments, models, data engines
    # TODO
    
if __name__ == "__main__":
    asyncio.run(main())
