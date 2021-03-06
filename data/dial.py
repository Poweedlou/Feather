# File contains API resources for JS


from flask_restful import reqparse, Resource, request
from flask import jsonify, send_file
import sys
from .db_funcs import (UserConnector,
                       DialogConnector,
                       MessageConnector,
                       FileConnector,
                       filetype,
                       commit)
from datetime import datetime
from .validators import *
from PIL import Image
from pathlib import Path


OK = {'status': 'OK'}, 200
# OK for returning


class PicturesResource(Resource):
    # This resource returns files (not URLs)
    @check(user_exists, correct_uid)
    def get(self, uid):
        # the only method
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('file_id', required=True)
            orig_id = parser.parse_args()['file_id']
            access, file_id = orig_id.split('_')
            access, file_id = int(access), int(file_id)
        except:
            return {'status': 'ER', 'reason': 'bad request'}, 400
        if access == -1:
            try:
                return send_file(f'user_imgs/{orig_id}.png',
                                 attachment_filename='avatar.png')
            except:
                return send_file(f'static/avatar.png')
        user_chats = UserConnector.from_id(uid).chats
        if access == -2:
            f = False
            for chat in user_chats:
                f = f or chat.id == file_id
            if not f:
                return {'status': 'ER', 'reason': 'no access'}, 401
            try:
                return send_file(f'user_imgs/{orig_id}.png',
                                 attachment_filename='avatar.png')
            except:
                return send_file(f'static/m_icon.png')
        file = FileConnector.from_id(file_id)
        if file.entry.file_access != access:
            return {'status': 'ER', 'reason': 'file not found'}, 404
        try:
            f = False
            for chat in user_chats:
                f = f or chat.id == access
            if not f:
                return {'status': 'ER', 'reason': 'no access'}, 401
            return send_file(f'user_imgs/{orig_id}',
                             attachment_filename=file.entry.filename)
        except:
            return {'status': 'ER', 'reason': 'file timed out'}, 401


class FilesResource(Resource):
    # This resource returns URLs for files
    @check(user_exists, correct_uid)
    def get(self, uid):
        # You can use URL to get a file
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('file_id', required=True)
            orig_id = parser.parse_args()['file_id']
            access, file_id = orig_id.split('_')
            access, file_id = int(access), int(file_id)
        except:
            return {'status': 'ER', 'reason': 'bad request'}, 400
        if access == -1:
            return jsonify({
                'status': 'OK',
                'result': {
                    'type': 'image',
                    'src': f'/api/pictures?uid={uid}&file_id={orig_id}'
                }
            })
        user_chats = UserConnector.from_id(uid).chats
        if access == -2:
            f = False
            for chat in user_chats:
                f = f or chat.id == file_id
            if not f:
                return {'status': 'ER', 'reason': 'no access'}, 401
            return jsonify({
                'status': 'OK',
                'result': {
                    'type': 'image',
                    'src': f'/api/pictures?uid={uid}&file_id={orig_id}'
                }
            })
        file = FileConnector.from_id(file_id)
        if file.entry.file_access != access:
            return {'status': 'ER', 'reason': 'file not found'}, 404

        f = False
        for chat in user_chats:
            f = f or chat.id == access
        if not f:
            return {'status': 'ER', 'reason': 'no access'}, 401
        return jsonify({
            'status': 'OK',
            'result': {
                'type': filetype(file_id),
                'src': f'/api/pictures?uid={uid}&file_id={orig_id}'
            }
        })


@check(user_exists, correct_uid)
class ChatsResource(Resource):
    # API resource for getting and creating chats
    def get(self, uid):
        # get list of your chats
        info = []
        user = UserConnector.from_id(uid)
        for dial in user.chats:
            dial_info = {'dialog_id': dial.id}
            mp = len(list(dial.users_id)) != 2
            if mp:
                pic = dial.entry.has_pic
                dial_info['picture'] = f'-2_{dial.id}' if pic else None
                dial_info['name'] = dial.entry.name
            else:
                a, b, *_ = dial.entry.users
                enemy = b if a.user_id == uid else a
                pic = enemy.user.has_pic
                id_ = enemy.user_id
                dial_info['picture'] = f'-1_{id_}' if pic else None
                dial_info['name'] = enemy.user.login
            info.append(dial_info)
        return {'status': 'OK', 'chats': info}, 200

    def post(self, uid):
        # Create a new chat
        json = request.get_json()
        users = set(json.get('users_id', []))
        logins = json.get('users_logins', [])
        not_exist = []
        for login in logins:
            user = UserConnector.from_login(login)
            if user is None:
                return ({'status': 'ER',
                         'reason': f'user {login} not found',
                         'login': login}, 404)
            users.add(user.id)
        if uid not in users:
            users.add(uid)
        for uid_ in users:
            guest = UserConnector.from_id(uid_)
            if guest is None:
                return ({'status': 'ER',
                         'reason': f'user {uid} not found',
                         'uid': uid}, 404)
        return {'status': 'OK',
                'id': DialogConnector.new(host_id=uid,
                                          name=json['name'],
                                          users_id=users).id}


class UserInfoResource(Resource):
    # This recource return info about users
    def get(self):
        # This can be used to find out if user exists
        parser = reqparse.RequestParser()
        parser.add_argument('uid', type=int, default=0)
        parser.add_argument('login', default='')
        parser.add_argument('exists', type=int, default=0)
        args = parser.parse_args()
        login = args['login']
        uid = args['uid']
        if args['exists']:
            f = False
            if login:
                f = UserConnector.exists_from_login(login)
            elif args['uid']:
                f = UserConnector.exists_from_id(uid)
            return '1' if f else '0'
        if login:
            user = UserConnector.from_login(login)
        elif uid:
            user = UserConnector.from_id(uid)
        else:
            return {'status': 'ER', 'reason': 'missing args'}, 400
        user_info = {'id': user.id,
                     'login': user.entry.login,
                     'pic': f'-1_{user.id}' if user.entry.has_pic else None,
                     'created_date': user.entry.created_date.isoformat()}
        return {'status': 'OK', "info": user_info}, 200


@check(user_exists, correct_uid)
class SelfResource(Resource):
    # This resource provides some extra funcions for your profile
    def get(self, uid):
        # Returns All information about you
        user = UserConnector.from_id(uid)
        user_info = {'id': user.id,
                     'login': user.entry.login,
                     'pic': f'-1_{user.id}' if user.entry.has_pic else None,
                     'created_date': user.entry.created_date.isoformat(),
                     'chats_id': [chat.id for chat in user.chats]}
        return {'status': 'OK', "info": user_info}, 200

    def post(self, uid):
        # Sets a new profile pic
        files = list(request.files.values())
        if not files:
            return {'status': 'ER', 'reason': 'no file provided'}, 400
        file = files[0]
        try:
            img = Image.open(file)
        except:
            return {'status': 'ER', 'reason': 'some image issue'}, 403
        else:
            if img.size[0] != img.size[1]:
                return {'status': 'ER', 'reason': 'image is not square'}, 403
            img.thumbnail((100, 100))
            img.save(f'user_imgs/-1_{uid}.png')
            UserConnector.from_id(uid).entry.has_pic = True
            commit()
        return OK

    def delete(self, uid):
        # You can kill yourself
        UserConnector.delete_by_id(uid)
        return OK


class MessageResource(Resource):
    # This resource works with messages
    @check(user_exists, correct_uid, dialog_exists, dialog_belongs_to_user)
    def get(self, uid, dial, dialog_id):
        # Returns messages of a chat
        parser = reqparse.RequestParser()
        parser.add_argument('offset', type=int, default=0)
        parser.add_argument('count', type=int, default=20)
        args = parser.parse_args()
        msgs = dial.get_messages(args['count'], args['offset'])
        return {'status': 'OK',
                'msgs': [m.to_dict() for m in msgs],
                'dialog_name': dial.entry.name}

    @check(user_exists, correct_uid, dialog_exists, dialog_belongs_to_user)
    def post(self, uid, dial, dialog_id):
        # Creates a message in a chat
        text = request.form['text']
        time = datetime.now()
        files = request.files.values()
        id = MessageConnector.new(
            user_id=uid,
            text=text,
            files=files,
            created_date=time,
            dialog_id=dialog_id).id
        return {'status': 'OK', 'id': id}

    @check(user_exists, correct_uid, message_exists, message_belongs_to_user)
    def delete(self, uid, message_id, msg):
        # Deletes your message
        msg.delete()
        return {'status': 'OK'}

    @check(user_exists, correct_uid, message_exists, message_belongs_to_user)
    def patch(self, uid, message_id, msg):
        # Edits your message
        msg.entry.text = request.form['text']
        return OK


@check(user_exists, correct_uid, dialog_exists, dialog_belongs_to_user)
class DialogResource(Resource):
    # This resource represents dialogs
    def get(self, uid, dialog_id, dial):
        # Returns information about dialogs
        info = {'id': dial.id,
                'pic': f'-2_{dial.id}' if dial.entry.has_pic else None,
                'name': dial.entry.name,
                'users_id': list(dial.users_id),
                'host_id': dial.entry.host_id}
        return {'status': 'OK', 'info': info}, 200

    def post(self, uid, dialog_id, dial):
        # Adds users to a dialog
        users = request.json['users_id']
        for guest_uid in users:
            if not UserConnector.exists_from_id(guest_uid):
                return {'status': 'ER',
                        'reason': f'user {guest_uid} not found'}, 404
        dial.add_users(users)
        return OK

    def delete(self, uid, dialog_id, dial):
        # Kicks you from a dialog
        dial.delete_users([uid])
        return OK


@check(user_exists, correct_uid, dialog_exists, dialog_hosted_by_user)
class HostedDialogResource(Resource):
    # Extra functions for a user, who hosts a dialog
    def patch(self, dial, **_):
        # Changes chat's name
        new_name = request.form.get('name')
        if new_name is None:
            return {'status': 'ER', 'reason': 'form arg "name" missing'}, 400
        dial.entry.name = new_name
        return OK

    def post(self, dialog_id, dial, **_):
        # Changes dialog's pic
        files = list(request.files.values())
        if not files:
            return {'status': 'ER', 'reason': 'no file provided'}, 400
        file = files[0]
        try:
            img = Image.open(file)
        except:
            return {'status': 'ER', 'reason': 'some image issue'}, 403
        else:
            if img.size[0] != img.size[1]:
                return {'status': 'ER', 'reason': 'image is not square'}, 403
            img.thumbnail((100, 100))
            img.save(f'user_imgs/-2_{dialog_id}.png')
            dial.entry.has_pic = True
            commit()
        return OK

    def delete(self, dial, **_):
        # Kicks users from chat
        try:
            dial.delete_users(request.json['users_id'])
            return OK
        except:
            er = 'kick list must be a json like {"users_id": [ids_to_kick]}'
            return {'status': 'ER',
                    'reason': er}, 400
