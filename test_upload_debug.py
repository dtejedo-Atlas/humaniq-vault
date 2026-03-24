import requests
import tempfile
import os

def test_upload_debug():
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
    
    # Create a simple text file (not PDF) to test
    cv_content = """CARLOS MENDOZA RODRIGUEZ
CFO & Director Financiero Senior
carlos.mendoza@corporativo.com | +52 55 1234 5678 | Ciudad de México, México

RESUMEN EJECUTIVO
Director Financiero con 15+ años de experiencia liderando transformaciones financieras en manufactura automotriz.

EXPERIENCIA PROFESIONAL
CFO - GRUPO AUTOMOTRIZ MEXICANO (2020-2024)
• Lideré transformación financiera de empresa con $2B USD en ingresos anuales
• Implementé SAP S/4HANA reduciendo costos operativos 15%

EDUCACIÓN
• MBA Finanzas - ITAM, México (2011)
• CPA - Instituto Mexicano de Contadores Públicos (2010)
"""
    
    # Test with text file first (should work)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
        temp_file.write(cv_content)
        temp_file_path = temp_file.name
    
    try:
        with open(temp_file_path, 'rb') as f:
            files = {
                'file': ('test_cv.txt', f.read(), 'text/plain')
            }
            
            headers = {'Authorization': f'Bearer {token}'}
            
            print("🔍 Testing upload with text file...")
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
            else:
                print("❌ Upload failed")
                try:
                    error_data = response.json()
                    print(f"Error: {error_data}")
                except:
                    print(f"Error text: {response.text[:500]}")
                    
    finally:
        try:
            os.unlink(temp_file_path)
        except:
            pass

if __name__ == "__main__":
    test_upload_debug()