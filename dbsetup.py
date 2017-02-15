from sqlalchemy        import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm    import sessionmaker

# connection to MySQL instance on 4KOffice (intranet)
engine   = create_engine('mysql+pymysql://python:python@192.168.1.149:3306/imageimprov', echo=False)
# engine  = create_engine('mysql+pymysql://python:python@104.154.227.232:3306/imageimprov', echo=False)
Session  = sessionmaker(bind=engine)
Base     = declarative_base()
metadata = Base.metadata
