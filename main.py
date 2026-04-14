import threading
import bot_free
import bot4

t1 = threading.Thread(target=bot_free.revisar_partidos)
t2 = threading.Thread(target=bot4.revisar_partidos)

t1.start()
t2.start()

t1.join()
t2.join()
