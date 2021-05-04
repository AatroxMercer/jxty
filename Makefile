DIR_CURR = $(shell pwd)
DIR_BIN  = ${DIR_CURR}/bin

.PHONY: client server clear sync

all:
	make client

client:
	python ${DIR_BIN}/jxty_client.py

server:
	python ${DIR_BIN}/jxty_server.py

clear:
	rm ./*/shadow

sync:
	scp ${DIR_BIN}/jxty_server.py root@8.140.145.229:/root/jxty_server.py