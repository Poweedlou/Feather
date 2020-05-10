from hashlib import pbkdf2_hmac
from pathlib import Path
from datetime import datetime
from csv import writer, reader


if __name__ != "__main__":
    from sys import path
    path.append(path[0] + '\\data')


from tables import *
from connections import Base, create_session, global_init


global_init('db/featherDB.sqlite')
session = create_session()


def hashed_password(password):
    return pbkdf2_hmac('sha512', bytes(password, 'u8'), bytes('bytes', 'u8'), 10)


def check_password(password, user_id):
    session = create_session()
    return session.query(User).get(user_id).hashed_password == hashed_password(password)


class BaseConnector:
    table = None
    table_attrs = set()
    def __init__(self, entry):
        self.id = entry.id
        self.entry = entry
    
    @classmethod
    def from_id(cls, id):
        try:
            return cls(session.query(cls.table).get(id))
        except:
            return None

    @classmethod
    def new(cls, table_attrs=None, **kwargs):
        entry = cls.table()
        if table_attrs is None:
            table_attrs = cls.table_attrs
        foo = table_attrs - set(kwargs.keys())
        if foo:
            raise TypeError(f'Wrong args. Not found: {foo}')
        for k in table_attrs:
            setattr(entry, k, kwargs[k])
        session.add(entry)
        session.commit()
        return cls(entry)

    @classmethod
    def exists_from_id(cls, id):
        return session.query(cls.table).get(id) is not None


class MessageConnector(BaseConnector):
    table = Message
    table_attrs = set(('text',
                       'user_id',
                       'created_date',
                       'dialog_id'))
    @classmethod
    def new(cls, files=[], **kwargs):
        msg = super().new(table_attrs=cls.table_attrs, **kwargs)
        for f in files:
            print(f)
            FileConnector.register_file(kwargs['dialog_id'], f, msg.id)
        return msg

    def to_dict(self):
        files = []
        for file in self.entry.files:
            d = {'filename': file.filename,
                 'file_id': f'{file.file_access}_{file.id}'}
            files.append(d)
        retval = {'id': self.id,
                  'text': self.entry.text,
                  'uid': self.entry.user_id,
                  'datetime': self.entry.created_date.isoformat(timespec='seconds'),
                  'files': files}
        return retval

    def delete(self):
        session.query(Message).filter(Message.id == self.id).delete()


class FileConnector(BaseConnector):
    table = File
    table_attrs = set(('filename',
                       'message_id',
                       'file_access'))

    @classmethod
    def register_file(cls, access, file, message_id):
        id = cls.new(filename=file.filename, message_id=message_id, file_access=access).id
        new_filename = f'{access}_{id}'
        file.save('user_imgs/' + new_filename)


class UserConnector(BaseConnector):
    table = User
    table_attrs = set(('login',
                       'email',
                       'password'))

    @classmethod
    def new(cls, **kwargs):
        user = super().new(table_attrs=cls.table_attrs, **kwargs)
        user.entry.hashed_password = hashed_password(kwargs['password'])
        return user

    def check_password(self, password):
        return hashed_password(password) == self.entry.hashed_password

    @classmethod
    def login(cls, login, password):
        entry = session.query(User).filter(User.login == login).first()
        if entry is None:
            return None
        user = cls(entry)
        if user.check_password(password):
            return user
        else:
            raise ValueError

    @property
    def chats(self):
        for each in self.entry.dialogs:
            yield DialogConnector(each.dialog)

    @staticmethod
    def exists_from_login(login):
        return session.query(User).filter(User.login == login).first() is not None

    @classmethod
    def from_login(cls, login):
        entry = session.query(User).filter(User.login == login).first()
        if entry is not None:
            return cls(entry)

    @staticmethod
    def delete_by_id(id):
        session.query(User).filter(User.id == id).delete()
        session.commit()


class DialogConnector(BaseConnector):
    table = Dialog
    table_attrs = set(('host_id', 'name'))

    @classmethod
    def new(cls, **kwargs):
        if kwargs['name'] is None:
            kwargs['name'] = 'Chat'
        dialog = super().new(table_attrs=cls.table_attrs, **kwargs)
        for id in kwargs['users_id']:
            entry = Connector()
            entry.user_id = id
            entry.dial_id = dialog.id
            session.add(entry)
        session.commit()
        return dialog

    @property
    def users(self):
        for each in self.entry.users:
            yield UserConnector(each.user)
    
    @property
    def users_id(self):
        for each in self.entry.users:
            yield each.user_id

    def get_messages(self, count, offset):
        query = session.query(Message).filter(Message.dialog_id == self.id).order_by(Message.id.desc()).offset(offset).limit(count)
        for each in query:
            yield MessageConnector(each)

    def add_users(self, users_id):
        for id in set(users_id) - set(self.users_id):
            entry = Connector()
            entry.user_id = id
            entry.dial_id = self.id
            session.add(entry)
        session.commit()

    def delete_users(self, users_id):
        session.query(Connector).filter(Connector.dial_id == self.id, Connector.user_id.in_(users_id)).delete()
        session.commit()
