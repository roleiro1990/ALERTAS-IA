import threading
import bot_free
import bot4

def run_free():
    while True:
        bot_free.revisar_partidos()

def run_premium():
    while True:
        bot4.revisar_partidos()

t1 = threading.Thread(target=run_free)
t2 = threading.Thread(target=run_premium)

t1.start()
t2.start()

t1.join()
t2.join()
