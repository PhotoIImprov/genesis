from sqlalchemy import Column, text
from sqlalchemy.types import DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from dbsetup import Base
import os

class TractionLog(Base):

    __tablename__ = 'tractionlog'

    id = Column(Integer, primary_key=True, autoincrement=True)
    header = Column(String(1000), nullable=True)
    referer = Column(String(1000), nullable=True)
    campaign = Column(String(100), nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    def __init__(self, *args, **kwargs):
        self.header = kwargs.get('header')
        self.referer = kwargs.get('referer')
        self.campaign = kwargs.get('campaign')

        # truncate these strings so they'll fit
        if self.header is not None:
            self.header = self.header[:1000]
        if self.referer is not None:
            self.referer = self.referer[:1000]
        if self.campaign is not None:
            self.campaign = self.campaign[:100]

