import logging

from run_from_cats import Bot

from settings import TOKEN


def main():
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)s][%(asctime)s]%(message)s',
                        datefmt='%H:%M:%S %d.%m.%Y')
    bot = Bot(TOKEN)
    bot.run()


if __name__ == '__main__':
    main()

