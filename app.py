from flask import Flask, request, jsonify
import os
from azure.storage.blob import BlobServiceClient, ContentSettings
import json
from werkzeug.utils import secure_filename
import tempfile
from flask_cors import CORS
import uuid
import jwt
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
CORS(app)

# Configure Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING_1')
BLOB_CONTAINER_NAME = "weez-users-info"  # Your container name
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

# Hardcoded JWT Secret - replace this with a strong random string in production
JWT_SECRET = "weez-auth-secure-jwt-key-2025-04-01"  # This is a random string for demonstration

# Get user details endpoint
@app.route('/api/user-profile/<email>', methods=['GET'])
def get_user_profile(email):
    try:
        # Verify the JWT token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            # Verify the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            # Check if token is for the requested user
            if payload['sub'] != email:
                return jsonify({"error": "Unauthorized access to another user's profile"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired", "details": "Please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token", "details": "Authentication failed"}), 401
        
        # Use the actual email as the folder path
        folder_path = email + '/'
        
        # Get user info from blob storage
        user_info_blob = folder_path + "userInfo.json"
        try:
            blob_client = container_client.get_blob_client(user_info_blob)
            user_info_data = blob_client.download_blob()
            user_info = json.loads(user_info_data.readall())
            
            # Check if profile picture exists
            profile_pic_blob = folder_path + "profilePic.png"
            profile_pic_url = None
            try:
                profile_pic_client = container_client.get_blob_client(profile_pic_blob)
                profile_pic_client.get_blob_properties()  # Will raise error if not exists
                profile_pic_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{profile_pic_blob}"
            except:
                profile_pic_url = "https://i.pinimg.com/736x/23/a6/1f/23a61f584822b8c7dbaebdca7c96da3e.jpg"
            
            # Build the response with needed profile fields
            profile_data = {
                "email": email,
                "full_name": user_info.get("name", ""),
                "created_at": user_info.get("createdAt", ""),
                "last_login": user_info.get("lastLogin", ""),
                "profile_picture": profile_pic_url,
                "profession": user_info.get("profession", ""),
                "gender": user_info.get("gender", ""),
                "bio": user_info.get("bio", ""),
                "age": user_info.get("age", 0),
                "email_verified": user_info.get("email_verified", False)
            }
            
            return jsonify(profile_data)
            
        except Exception as e:
            return jsonify({"error": "User not found or error retrieving profile", "details": str(e)}), 404
        
    except Exception as e:
        print(f"Error retrieving user profile: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Update user profile endpoint
@app.route('/api/user-profile/<email>', methods=['PUT'])
def update_user_profile(email):
    try:
        # Verify the JWT token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            # Verify the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            # Check if token is for the requested user
            if payload['sub'] != email:
                return jsonify({"error": "Unauthorized access to update another user's profile"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired", "details": "Please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token", "details": "Authentication failed"}), 401
        
        # Parse update data
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Use the actual email as the folder path
        folder_path = email + '/'
        
        # Get user info from blob storage
        user_info_blob = folder_path + "userInfo.json"
        try:
            blob_client = container_client.get_blob_client(user_info_blob)
            user_info_data = blob_client.download_blob()
            user_info = json.loads(user_info_data.readall())
            
            # Update user info with new data
            if 'full_name' in data:
                user_info['name'] = data['full_name']
            if 'profession' in data:
                user_info['profession'] = data['profession']
            if 'gender' in data:
                user_info['gender'] = data['gender']
            if 'bio' in data:
                user_info['bio'] = data['bio']
            if 'age' in data and isinstance(data['age'], int):
                user_info['age'] = data['age']
            
            # Upload updated user info
            blob_client.upload_blob(
                json.dumps(user_info),
                overwrite=True,
                content_settings=ContentSettings(content_type='application/json')
            )
            
            return jsonify({"message": "Profile updated successfully"})
            
        except Exception as e:
            return jsonify({"error": "User not found or error updating profile", "details": str(e)}), 404
        
    except Exception as e:
        print(f"Error updating user profile: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Upload profile picture endpoint with email parameter
@app.route('/api/upload-profile-pic/<email>', methods=['POST'])
def upload_profile_pic(email):
    try:
        # Verify the JWT token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            # Verify the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            # Check if token is for the requested user
            if payload['sub'] != email:
                return jsonify({"error": "Unauthorized access to update another user's profile picture"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired", "details": "Please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token", "details": "Authentication failed"}), 401
        
        # Check if file was uploaded
        if 'profilePic' not in request.files:
            return jsonify({"error": "No file uploaded", "details": "profilePic field is required"}), 400
        
        file = request.files['profilePic']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Use the actual email as the folder path
        folder_path = email + '/'
        
        # Save file to a temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)
        temp_file.close()
        
        # Upload to Azure Blob Storage
        profile_pic_blob = folder_path + "profilePic.png"
        blob_client = container_client.get_blob_client(profile_pic_blob)
        
        with open(temp_file.name, "rb") as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type='image/png')
            )
        
        # Remove the temporary file
        os.unlink(temp_file.name)
        
        # Get the URL of the uploaded profile picture
        profile_pic_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{profile_pic_blob}"
        
        return jsonify({
            "message": "Profile picture uploaded successfully",
            "profile_picture_url": profile_pic_url
        })
        
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Check if user exists endpoint
@app.route('/api/user/check', methods=['GET'])
def check_user_exists():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email parameter is required"}), 400
    
    try:
        # Use the actual email as the folder path
        folder_path = email + '/'
        
        # Check if userInfo.json exists for this user
        user_info_blob = folder_path + "userInfo.json"
        exists = False
        
        # List blobs to check if this path exists
        blobs = container_client.list_blobs(name_starts_with=folder_path)
        for blob in blobs:
            if blob.name == user_info_blob:
                exists = True
                break
        
        return jsonify({"exists": exists})
    except Exception as e:
        print(f"Error checking if user exists: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Register user endpoint
@app.route('/api/register', methods=['POST'])
def register_user():
    try:
        data = request.json
        email = data.get('email')
        full_name = data.get('fullName')
        id_token = data.get('password')  # Using the token as password
        google_id = data.get('googleId')
        
        if not email or not id_token:
            return jsonify({"error": "Email and ID token are required"}), 400
        
        # Use the actual email as the folder path
        folder_path = email + '/'
        
        # Create a user info object
        user_info = {
            "email": email,
            "name": full_name,
            "googleId": google_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "lastLogin": datetime.now(timezone.utc).isoformat()
        }
        
        # Upload user info to blob storage
        user_info_blob = folder_path + "userInfo.json"
        blob_client = container_client.get_blob_client(user_info_blob)
        
        blob_client.upload_blob(
            json.dumps(user_info),
            overwrite=True,
            content_settings=ContentSettings(content_type='application/json')
        )
        
        # Generate JWT token for authentication
        token = generate_jwt_token(email)
        
        return jsonify({
            "message": "User registered successfully",
            "token": token,
            "userInfo": user_info
        })
    except Exception as e:
        print(f"Error registering user: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Google login endpoint
@app.route('/api/login/google', methods=['POST'])
def login_google():
    try:
        data = request.json
        email = data.get('email')
        id_token = data.get('idToken')
        
        if not email or not id_token:
            return jsonify({"error": "Email and ID token are required"}), 400
        
        # Use the actual email as the folder path
        folder_path = email + '/'
        
        # Check if user exists
        user_info_blob = folder_path + "userInfo.json"
        try:
            blob_client = container_client.get_blob_client(user_info_blob)
            user_info_data = blob_client.download_blob()
            user_info = json.loads(user_info_data.readall())
            
            # Update last login
            user_info["lastLogin"] = datetime.now(timezone.utc).isoformat()
            
            # Upload updated user info
            blob_client.upload_blob(
                json.dumps(user_info),
                overwrite=True,
                content_settings=ContentSettings(content_type='application/json')
            )
            
            # Generate JWT token for authentication
            token = generate_jwt_token(email)
            
            # Check if profile picture exists
            profile_pic_blob = folder_path + "profilePic.png"
            profile_pic_url = None
            try:
                profile_pic_client = container_client.get_blob_client(profile_pic_blob)
                profile_pic_client.get_blob_properties()  # Will raise error if not exists
                profile_pic_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{profile_pic_blob}"
            except:
                pass
            
            return jsonify({
                "message": "Login successful",
                "token": token,
                "userInfo": user_info,
                "profilePicUrl": profile_pic_url
            })
            
        except Exception as e:
            return jsonify({"error": "User not found or authentication failed"}), 401
        
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Upload profile picture endpoint
@app.route('/api/profile-picture', methods=['POST'])
def upload_profile_picture():
    try:
        # Check if Authorization header is present
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        
        # Get the token
        token = auth_header.split(' ')[1]
        
        # For now, get email from form data
        user_email = request.form.get('email')
        if not user_email:
            return jsonify({"error": "Email is required"}), 400
            
        # Check if file was uploaded
        if 'profile_pic' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['profile_pic']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Use the actual email as the folder path
        folder_path = user_email + '/'
        
        # Save file to a temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)
        temp_file.close()
        
        # Upload to Azure Blob Storage
        profile_pic_blob = folder_path + "profilePic.png"
        blob_client = container_client.get_blob_client(profile_pic_blob)
        
        with open(temp_file.name, "rb") as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type='image/png')
            )
        
        # Remove the temporary file
        os.unlink(temp_file.name)
        
        # Get the URL of the uploaded profile picture
        profile_pic_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{profile_pic_blob}"
        
        return jsonify({
            "message": "Profile picture uploaded successfully",
            "profilePicUrl": profile_pic_url
        })
        
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Helper function to generate JWT token
def generate_jwt_token(email):
    payload = {
        'sub': email,
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(days=1)  # Token expires in 1 day
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token

if __name__ == '__main__':
    # Create container if it doesn't exist
    try:
        container_client = blob_service_client.create_container(BLOB_CONTAINER_NAME)
    except:
        pass  # Container already exists
    
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
