from flask_restful import reqparse, Resource
from flask import jsonify, session
import sys
from .db_funcs import UserConnector

class AuthResource(Resource):
    # Log in
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('login', required=True)
        parser.add_argument('password', required=True)
        args = parser.parse_args()
        try:
            user = UserConnector.login(args['login'], args['password'])
            if user is not None:
                session['logged_in'] = user.id
                return jsonify({'status': "OK",
                                'uid': user.id})
            else:
                return jsonify({'status': "ER",
                                'reason': 'wrong password'}), 401
        except:
            return jsonify({'status': "ER",
                            'reason': 'user not found'}), 404
    # Sign up
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('login', required=True)
        parser.add_argument('email', required=True)
        parser.add_argument('password', required=True)
        args = parser.parse_args()
        try: 
            uid = UserConnector.new_user(args['login'], args['email'], args['password']).id
            session['logged_in'] = uid
            return jsonify({'status': "OK", 'uid': uid})
        except BaseException:
            return jsonify({'status': "ER",
                            'reason': 'login or email is already taken'}), 409