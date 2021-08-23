FROM python:3

WORKDIR ./

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY binance-trade-bot/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY ../../../Downloads/BTB-manager-telegram-ddd6c6a285192a5505249f9a13ecad783ee8c453 .

CMD [ "python", "-m", "btb_manager_telegram", "-p", "./binance-trade-bot/"]
