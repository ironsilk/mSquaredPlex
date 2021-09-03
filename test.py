import os

from utils import make_client, torr_cypher

print(os.getenv('TORR_HASH_KEY'))
torr_client = make_client()
x = """5Yaqz+SsrJ/LaosYlJYysm4jcE3jp61kUCf5YuXLRSKZcAZUZqQaK0QuoaIY3Ox6HcKprGHJQZPFgrwXkMUWua7NqxqHSu7KEwotxs/gKO4e8VwKLv/kPJknKKN3p93GsPYgO42k5uuyrbwGm0X/vP5sxJExbQ== """
print(torr_cypher.decrypt(x))

# doesnt work, dunno why.
# docker run -it --rm --network host exoplatform/mysqltuner --host 192.168.1.99 --user root --pass pass --forcemem 128