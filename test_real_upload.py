import requests

def test_real_docx_upload():
    base_url = "https://atlas-recruiting-ai.preview.emergentagent.com"
    
    # Login first
    login_data = {
        "email": "admin@atlas.com",
        "password": "password123"
    }
    
    login_response = requests.post(
        f"{base_url}/api/auth/login",
        json=login_data,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.status_code}")
        return
    
    token = login_response.json()['access_token']
    print("✅ Login successful")
    
    # Upload the DOCX file
    try:
        with open('/app/test_cv.docx', 'rb') as f:
            files = {
                'file': ('carlos_mendoza_cfo.docx', f.read(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            }
            
            headers = {'Authorization': f'Bearer {token}'}
            
            print("🔍 Testing upload with DOCX file...")
            response = requests.post(
                f"{base_url}/api/candidates/upload-resume",
                files=files,
                headers=headers,
                timeout=90
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print("✅ Upload successful!")
                print(f"Status: {result.get('status')}")
                print(f"Candidate ID: {result.get('candidate_id')}")
                parsed_data = result.get('parsed_data', {})
                print(f"Parsed name: {parsed_data.get('full_name')}")
                print(f"Parsed email: {parsed_data.get('email')}")
                print(f"Parsed company: {parsed_data.get('current_company')}")
                print(f"Parsed title: {parsed_data.get('current_title')}")
                
                # Test duplicate detection by uploading same file again
                print("\n🔍 Testing duplicate detection...")
                duplicate_response = requests.post(
                    f"{base_url}/api/candidates/upload-resume",
                    files=files,
                    headers=headers,
                    timeout=90
                )
                
                print(f"Duplicate test status: {duplicate_response.status_code}")
                if duplicate_response.status_code == 200:
                    dup_result = duplicate_response.json()
                    print(f"Duplicate status: {dup_result.get('status')}")
                    if dup_result.get('duplicates'):
                        max_confidence = max(d.get('confidence', 0) for d in dup_result['duplicates'])
                        print(f"Max duplicate confidence: {max_confidence:.2f}")
                
            else:
                print("❌ Upload failed")
                try:
                    error_data = response.json()
                    print(f"Error: {error_data}")
                except:
                    print(f"Error text: {response.text[:500]}")
                    
    except Exception as e:
        print(f"Exception: {str(e)}")

if __name__ == "__main__":
    test_real_docx_upload()