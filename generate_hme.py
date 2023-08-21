import main
import asyncio

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main.generate())
    except KeyboardInterrupt:
        pass
