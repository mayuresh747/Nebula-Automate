"""
Refresh authentication token from browser localStorage

This script uses Playwright to fetch a fresh auth token from the nebulaONE browser session.
"""

import os
import re
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv, set_key

def get_fresh_token():
    """Fetch fresh auth token from browser localStorage."""
    print("🔄 Fetching fresh authentication token from browser...")
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Navigate to nebulaONE
            print("   Opening nebulaONE...")
            page.goto("https://nebulaone-pilot.uw.edu", wait_until="domcontentloaded")
            
            # Wait a bit for auth to load
            page.wait_for_timeout(3000)
            
            # Try to get token from localStorage
            token = page.evaluate("""
                () => {
                    try {
                        // Try direct n1aiToken first
                        let token = localStorage.getItem('n1aiToken');
                        if (token) {
                            // Remove surrounding quotes if present
                            if (token.startsWith('"') && token.endsWith('"')) {
                                token = token.substring(1, token.length - 1);
                            }
                            return token;
                        }
                        
                        // Fallback: try persist:auth
                        const auth = localStorage.getItem('persist:auth');
                        if (auth) {
                            const parsed = JSON.parse(auth);
                            token = parsed.n1aiToken;
                            if (token && token.startsWith('"') && token.endsWith('"')) {
                                token = token.substring(1, token.length - 1);
                            }
                            return token;
                        }
                        return null;
                    } catch (e) {
                        return null;
                    }
                }
            """)
            
            if not token or token == 'null':
                print("   ⚠️  No token found in localStorage. You may need to sign in.")
                print("   Opening sign-in page...")
                
                # Try to click sign in button OR wait for existing redirect
                try:
                    # Check if already on login page (auto-redirect may have happened)
                    current_url = page.url
                    if 'login.microsoftonline.com' in current_url or 'duosecurity.com' in current_url:
                        print("   ✅ Already redirected to login page")
                        print("   📋 Please complete sign-in in the browser window...")
                        print("   ⏳ Waiting up to 2 minutes for authentication...")
                    else:
                        # Try to click sign in button
                        page.click('text="Sign in with Microsoft"', timeout=20000)
                        print("   ✅ Sign-in page opened")
                        print("   📋 Please complete sign-in in the browser window...")
                        print("   ⏳ Waiting up to 2 minutes for authentication...")
                    
                    # Wait for redirect back to main page (2 minutes timeout)
                    # After login, user is redirected to /chat or /chat/onechat
                    page.wait_for_url("**/chat**", timeout=120000)
                    print("   ✅ Sign-in detected, retrieving token...")
                    page.wait_for_timeout(5000)  # Wait a bit longer for token to be set
                    
                    # Try to get token again
                    token = page.evaluate("""
                        () => {
                            try {
                                // Try direct n1aiToken first
                                let token = localStorage.getItem('n1aiToken');
                                if (token) {
                                    if (token.startsWith('"') && token.endsWith('"')) {
                                        token = token.substring(1, token.length - 1);
                                    }
                                    return token;
                                }
                                
                                // Fallback: try persist:auth
                                const auth = localStorage.getItem('persist:auth');
                                if (auth) {
                                    const parsed = JSON.parse(auth);
                                    token = parsed.n1aiToken;
                                    if (token && token.startsWith('"') && token.endsWith('"')) {
                                        token = token.substring(1, token.length - 1);
                                    }
                                    return token;
                                }
                                return null;
                            } catch (e) {
                                return null;
                            }
                        }
                    """)
                except Exception as e:
                    print(f"   ⚠️  Sign-in timeout or error: {e}")
                    print("   💡 Tip: Make sure you're logged into nebulaONE in your browser")
            
            browser.close()
            
            if token and token != 'null':
                print("   ✅ Token retrieved successfully!")
                return token
            else:
                print("   ❌ Failed to retrieve token")
                return None
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            browser.close()
            return None


def update_env_file(token):
    """Update .env file with new token."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    if not os.path.exists(env_path):
        print(f"   ⚠️  .env file not found at {env_path}")
        return False
    
    try:
        # Update the token in .env file
        set_key(env_path, 'NEBULA_AUTH_TOKEN', token)
        print(f"   ✅ Updated .env file with new token")
        return True
    except Exception as e:
        print(f"   ❌ Error updating .env file: {e}")
        return False


def refresh_token():
    """Main function to refresh token and update .env file."""
    print("\n" + "="*60)
    print("Token Refresh Utility")
    print("="*60 + "\n")
    
    token = get_fresh_token()
    
    if token:
        if update_env_file(token):
            print("\n✅ Token refresh complete!")
            return True
        else:
            print("\n⚠️  Token retrieved but failed to update .env file")
            print(f"   Token: {token[:50]}...")
            return False
    else:
        print("\n❌ Token refresh failed")
        return False


if __name__ == "__main__":
    refresh_token()
