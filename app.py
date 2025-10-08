import os
from flask import Flask, request, jsonify
import requests
import re
import threading
import logging
from datetime import datetime

app = Flask(__name__)

# Use environment variables for sensitive data
BOT_TOKEN = os.getenv('BOT_TOKEN', '8195959244:AAHGnTQcrfd2WdHEGlKV4zeBfAq26enPEnU')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_card_data(cc, mm, yy, cvv):
    """Validate card data format"""
    if not re.match(r'^\d{16}$', cc):
        return False, "Invalid card number"
    if not re.match(r'^\d{2}$', mm) or not (1 <= int(mm) <= 12):
        return False, "Invalid month"
    if not re.match(r'^\d{2,4}$', yy):
        return False, "Invalid year"
    if not re.match(r'^\d{3,4}$', cvv):
        return False, "Invalid CVV"
    return True, "Valid"

def safe_request(session, url, method='GET', **kwargs):
    """Safe request wrapper with error handling"""
    try:
        if method.upper() == 'POST':
            response = session.post(url, **kwargs)
        else:
            response = session.get(url, **kwargs)
        return response, None
    except Exception as e:
        logger.error(f"Request error for {url}: {str(e)}")
        return None, str(e)

# Your existing gateway functions remain the same...
# [stripe_auth_check, braintree_check, stripe_charge_check, get_bin_info]

def background_task(chat_id, message_id, full_cc_string, gateway_function, gateway_name):
    """Enhanced background task with better logging"""
    logger.info(f"Processing card for {gateway_name}, Chat: {chat_id}")
    
    try:
        cc, mm, yy, cvv = full_cc_string.split('|')
        
        # Validate card data
        is_valid, validation_msg = validate_card_data(cc, mm, yy, cvv)
        if not is_valid:
            final_message = f"""<b>Invalid Card Format ❌</b>\n\n<b>Card:</b> <code>{full_cc_string}</code>\n<b>Error:</b> {validation_msg}"""
            payload = {'chat_id': chat_id, 'message_id': message_id, 'text': final_message, 'parse_mode': 'HTML'}
            requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
            return
        
        check_result = gateway_function(cc, mm, yy, cvv)
        bin_info = get_bin_info(cc[:6])
        
        status = check_result.get('status', 'Declined')
        response_message = check_result.get('response', 'No response.')
        brand = bin_info.get('brand', 'Unknown')
        card_type = bin_info.get('type', 'Unknown')
        country = bin_info.get('country_name', 'Unknown')
        country_flag = bin_info.get('country_flag', '')
        bank = bin_info.get('bank', 'Unknown')
        
        if status == "Approved":
            final_message = f"""<b>Approved ✅ ({gateway_name})</b>\n\n<b>Card:</b> <code>{full_cc_string}</code>\n<b>Response:</b> {response_message}\n\n<b>Info:</b> {brand} - {card_type}\n<b>Issuer:</b> {bank}\n<b>Country:</b> {country} {country_flag}"""
        else:
            final_message = f"""<b>Declined ❌ ({gateway_name})</b>\n\n<b>Card:</b> <code>{full_cc_string}</code>\n<b>Response:</b> {response_message}\n\n<b>Info:</b> {brand} - {card_type}\n<b>Issuer:</b> {bank}\n<b>Country:</b> {country} {country_flag}"""
        
        payload = {'chat_id': chat_id, 'message_id': message_id, 'text': final_message, 'parse_mode': 'HTML'}
        requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        
    except Exception as e:
        logger.error(f"Background task error: {str(e)}")
        error_message = f"""<b>Processing Error ⚠️</b>\n\n<b>Card:</b> <code>{full_cc_string}</code>\n<b>Error:</b> System error occurred"""
        payload = {'chat_id': chat_id, 'message_id': message_id, 'text': error_message, 'parse_mode': 'HTML'}
        requests.post(TELEGRAM_API_URL, json=payload, timeout=10)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

# Your existing routes remain the same...
# [stripe_auth_endpoint, braintree_endpoint, stripe_charge_endpoint]

if __name__ == '__main__':
    # Consider using production WSGI server like Gunicorn
    app.run(host='0.0.0.0', port=10000, debug=False)
