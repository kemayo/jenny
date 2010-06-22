#!/usr/bin/python

import sqlite3
import datetime

__author__ = 'David Lynch (kemayo at gmail dot com)'
__version__ = '0.1'
__copyright__ = 'Copyright (c) 2009 David Lynch'
__license__ = 'New BSD License'

class SequenceStore(object):
    """A store for values by date, sqlite-backed"""
    def __init__(self, storepath):
        """Initializes the store; creates tables if required

        storepath is the path to a sqlite database, and will be created
        if it doesn't already exist. (":memory:" will store everything
        in-memory, if you only need to use this as a temporary thing).
        """
        store = sqlite3.connect(storepath)
        self.store = store
        c = store.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS store (id INTEGER PRIMARY KEY, type TEXT, date TEXT, value TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS bytype on store (type, date DESC)""")
        self.store.commit()
        c.close()
    def add(self, type, value):
        """Add a value to the store, at the current time

        type is a string that the value will be associated with
        value is the value to be stored
        """
        c = self.store.cursor()
        c.execute("""INSERT INTO store (type, date, value) VALUES (?, DATETIME(), ?)""", (type, value,))
        self.store.commit()
        c.close()
    def get(self, type, parse_dates = True, value_function = lambda x: x, order = "DESC"):
        """Fetch a given type's data

        type is a string to fetch all associated values for
        parse_dates is a boolean; if true, the sqlite date will be
            turned into a datetime object
        value_function is a function to apply to the returned values

        returns a list of tuples in the form (datetime, value)
        """
        c = self.store.cursor()
        c.execute("""SELECT date, value FROM store WHERE type = ? ORDER BY date %s""" % order, (type,))
        rows = c.fetchall()
        c.close()
        if parse_dates:
            rows = [(datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S"), value_function(value)) for date,value in rows]
        return rows
