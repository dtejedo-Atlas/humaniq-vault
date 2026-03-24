import requests
import sys
import json
import time
import tempfile
import os
from datetime import datetime
from pathlib import Path

class AtlasRealWorldTester:
    def __init__(self, base_url="https://atlas-recruiting-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.admin_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.candidate_ids = []

    def log_test(self, name, success, details="", critical=False):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "critical": critical,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASSED" if success else "❌ FAILED"
        critical_marker = " [CRITICAL]" if critical else ""
        print(f"{status}{critical_marker} - {name}")
        if details:
            print(f"   Details: {details}")

    def create_super_admin_user(self):
        """Create a super admin user for testing"""
        admin_data = {
            "email": "superadmin@atlas.com",
            "password": "SuperAdmin123!",
            "name": "Super Admin Test",
            "role": "super_admin"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/register",
                json=admin_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                # Now login as super admin
                login_response = requests.post(
                    f"{self.base_url}/api/auth/login",
                    json={"email": admin_data["email"], "password": admin_data["password"]},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if login_response.status_code == 200:
                    result = login_response.json()
                    self.admin_token = result['access_token']
                    self.log_test("Super Admin Setup", True, "Super admin user created and authenticated")
                    return True
                else:
                    self.log_test("Super Admin Setup", False, f"Login failed: {login_response.status_code}")
                    return False
            else:
                # User might already exist, try to login
                login_response = requests.post(
                    f"{self.base_url}/api/auth/login",
                    json={"email": admin_data["email"], "password": admin_data["password"]},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if login_response.status_code == 200:
                    result = login_response.json()
                    self.admin_token = result['access_token']
                    self.log_test("Super Admin Setup", True, "Super admin user already exists, authenticated")
                    return True
                else:
                    self.log_test("Super Admin Setup", False, f"User exists but login failed: {login_response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_test("Super Admin Setup", False, f"Exception: {str(e)}")
            return False

    def authenticate(self):
        """Authenticate with regular test user"""
        login_data = {
            "email": "admin@atlas.com",
            "password": "password123"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json=login_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.token = result['access_token']
                self.log_test("Authentication", True, "Successfully authenticated")
                return True
            else:
                self.log_test("Authentication", False, f"Status: {response.status_code}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("Authentication", False, f"Exception: {str(e)}", critical=True)
            return False

    def create_realistic_pdf_content(self, profile_type="cfo"):
        """Create realistic CV content"""
        if profile_type == "cfo":
            return """CARLOS MENDOZA RODRIGUEZ
CFO & Director Financiero Senior
carlos.mendoza@corporativo.com | +52 55 1234 5678 | Ciudad de México, México
LinkedIn: linkedin.com/in/carlosmendoza-cfo

RESUMEN EJECUTIVO
Director Financiero con 15+ años de experiencia liderando transformaciones financieras en manufactura automotriz y bienes de consumo. Especialista en M&A, optimización de costos y implementación de sistemas ERP. MBA en Finanzas, CPA certificado.

EXPERIENCIA PROFESIONAL

CFO - GRUPO AUTOMOTRIZ MEXICANO (2020-2024)
• Lideré transformación financiera de empresa con $2B USD en ingresos anuales
• Implementé SAP S/4HANA reduciendo costos operativos 15% ($30M anuales)
• Dirigí 3 adquisiciones estratégicas por valor de $500M USD
• Gestión de equipo de 45 profesionales financieros en 8 países
• Mejora de EBITDA margin de 12% a 18% en 4 años

Director de Finanzas - NESTLE MEXICO (2016-2020)
• P&L responsibility para 8 categorías de productos ($800M revenue)
• Optimización working capital, mejorando cash flow 25% ($50M)
• Implementación centros servicios compartidos (SSC) para LATAM
• Liderazgo proyectos digitales: RPA, analytics, forecasting

Gerente Financiero Senior - COCA-COLA FEMSA (2012-2016)
• Financial planning & analysis para operaciones México
• Consolidación financiera de 12 plantas manufactureras
• Business partnering con operaciones, marketing, supply chain
• Proyectos automatización: reducción 40% tiempo cierre mensual

EDUCACIÓN
• MBA Finanzas - ITAM, México (2011)
• CPA - Instituto Mexicano de Contadores Públicos (2010)
• Licenciatura Contaduría Pública - UNAM (2008)

CERTIFICACIONES Y HABILIDADES
• Liderazgo financiero, Strategic planning, M&A
• SAP S/4HANA, Oracle ERP, Power BI, Advanced Excel
• Lean Six Sigma Black Belt, Project Management
• Inglés nativo, Francés intermedio, Portugués básico

LOGROS DESTACADOS
• Reducción costos operativos: $80M+ en carrera profesional
• 3 adquisiciones exitosas por $500M+ valor total
• Implementación 5 sistemas ERP en diferentes compañías
• Certificación ISO 9001, SOX compliance en empresas públicas"""

        elif profile_type == "operations_director":
            return """MARIA ELENA GARCIA LOPEZ
Directora de Operaciones | Supply Chain & Manufacturing Expert
maria.garcia@operaciones.com | +52 81 9876 5432 | Monterrey, Nuevo León
LinkedIn: linkedin.com/in/mariagarcia-operations

PERFIL EJECUTIVO
Directora de Operaciones con 12+ años transformando operaciones en retail, manufactura y logística. Experta en supply chain optimization, lean manufacturing y transformación digital. Track record de reducción de costos >$50M y mejora de KPIs operacionales.

TRAYECTORIA PROFESIONAL

Directora de Operaciones - LIVERPOOL (2021-2024)
• Optimización supply chain para red de 120+ tiendas departamentales
• Implementación WMS/TMS reduciendo inventario 20% ($40M)
• Liderazgo de 200+ colaboradores en logística y distribución
• Mejora KPIs: On-Time Delivery 98%, Fill Rate 95%, Cost per shipment -12%
• Digitalización: IoT, predictive analytics, automated replenishment

Gerente Supply Chain - CEMEX (2018-2021)
• Gestión supply chain región Norte México (15 plantas, 500+ camiones)
• Optimización rutas distribución: ahorro $8M anuales en transporte
• Implementación IoT en flotilla: reducción 25% costos mantenimiento
• Certificaciones ISO 9001, ISO 14001, OHSAS 18001
• Liderazgo equipos multiculturales (México, USA, Colombia)

Coordinadora Producción - GRUPO BIMBO (2015-2018)
• Supervisión 3 plantas producción (capacidad 500 ton/día)
• Implementación metodologías Lean: mejora 15% eficiencia OEE
• Gestión inventarios materias primas: reducción 30% stock
• Planeación demanda: forecast accuracy 92%

FORMACIÓN ACADÉMICA
• Maestría Ingeniería Industrial - ITESM (2014)
• Ingeniería Industrial - UANL (2012)
• Six Sigma Black Belt Certification - ASQ (2019)
• Supply Chain Management Certificate - MIT (2020)

COMPETENCIAS TÉCNICAS
• Supply Chain Management, Lean Manufacturing, Six Sigma
• SAP MM/PP/WM, Oracle SCM, WMS Manhattan, TMS
• Power BI, Tableau, Advanced Excel, Python básico
• Project Management (PMP), Change Management
• Inglés fluido, Alemán intermedio

LOGROS CUANTIFICABLES
• Reducción costos operativos: $50M+ en carrera
• Mejora OEE promedio: 15% en todas las operaciones
• Implementación 8 proyectos Lean/Six Sigma exitosos
• Certificación plantas: 100% compliance ISO standards"""

        return self.create_realistic_pdf_content("cfo")  # Default

    def test_real_cv_upload_flow(self):
        """Test END-TO-END CV upload with realistic content"""
        print("\n🔍 Testing Real CV Upload Flow...")
        
        cv_content = self.create_realistic_pdf_content("cfo")
        
        # Create a temporary file to simulate real file upload
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(cv_content)
            temp_file_path = temp_file.name
        
        try:
            # Read the file as binary for upload
            with open(temp_file_path, 'rb') as f:
                files = {
                    'file': ('carlos_mendoza_cfo.pdf', f.read(), 'application/pdf')
                }
                
                headers = {'Authorization': f'Bearer {self.token}'}
                
                response = requests.post(
                    f"{self.base_url}/api/candidates/upload-resume",
                    files=files,
                    headers=headers,
                    timeout=90  # AI parsing takes time
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Check parsing results
                    parsed_data = result.get('parsed_data', {})
                    candidate_id = result.get('candidate_id')
                    status = result.get('status', '')
                    
                    if candidate_id:
                        self.candidate_ids.append(candidate_id)
                    
                    # Evaluate parsing quality
                    name_extracted = bool(parsed_data.get('full_name'))
                    email_extracted = bool(parsed_data.get('email'))
                    company_extracted = bool(parsed_data.get('current_company'))
                    title_extracted = bool(parsed_data.get('current_title'))
                    experience_extracted = bool(parsed_data.get('years_experience'))
                    
                    parsing_score = sum([name_extracted, email_extracted, company_extracted, title_extracted, experience_extracted])
                    
                    success = parsing_score >= 3 and candidate_id is not None
                    
                    self.log_test(
                        "Real CV Upload & Parsing", 
                        success,
                        f"Status: {status}, Parsed {parsing_score}/5 fields, Candidate ID: {candidate_id[:8] if candidate_id else 'None'}...",
                        critical=True
                    )
                    
                    # Test AI classification if upload succeeded
                    if success and candidate_id:
                        time.sleep(3)  # Allow processing
                        self.test_ai_classification_accuracy(candidate_id)
                    
                    return success
                else:
                    error_detail = ""
                    try:
                        error_data = response.json()
                        error_detail = error_data.get('detail', 'Unknown error')
                    except:
                        error_detail = response.text[:200]
                    
                    self.log_test("Real CV Upload & Parsing", False, f"Status: {response.status_code} - {error_detail}", critical=True)
                    return False
                    
        except Exception as e:
            self.log_test("Real CV Upload & Parsing", False, f"Exception: {str(e)}", critical=True)
            return False
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file_path)
            except:
                pass

    def test_ai_classification_accuracy(self, candidate_id):
        """Test Atlas AI classification for business relevance"""
        try:
            response = requests.post(
                f"{self.base_url}/api/atlas/classify/{candidate_id}",
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=60
            )
            
            if response.status_code == 200:
                classification = response.json()
                
                industry = classification.get('industry', '').lower()
                functional_area = classification.get('functional_area', '').lower()
                seniority = classification.get('seniority', '').lower()
                confidence = classification.get('confidence_score', 0)
                
                # For CFO profile, expect relevant classifications
                industry_relevant = any(term in industry for term in ['manufacturing', 'manufactura', 'automotive', 'automotriz', 'consumer', 'consumo'])
                area_relevant = any(term in functional_area for term in ['finance', 'finanzas', 'accounting', 'contabilidad', 'general management', 'direccion'])
                seniority_relevant = seniority in ['director', 'c_level', 'vp']
                
                # Business relevance score
                relevance_score = sum([industry_relevant, area_relevant, seniority_relevant])
                
                success = relevance_score >= 2 and confidence > 0.6
                
                self.log_test(
                    "AI Classification Accuracy",
                    success,
                    f"Industry: {classification.get('industry')}, Area: {classification.get('functional_area')}, Seniority: {seniority}, Confidence: {confidence:.2f}, Relevance: {relevance_score}/3",
                    critical=True
                )
                
                return success
            else:
                self.log_test("AI Classification Accuracy", False, f"Status: {response.status_code}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("AI Classification Accuracy", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_duplicate_detection_accuracy(self):
        """Test duplicate detection with realistic variations"""
        print("\n🔍 Testing Duplicate Detection Accuracy...")
        
        # Create a variant of the same CFO profile
        original_content = self.create_realistic_pdf_content("cfo")
        variant_content = original_content.replace(
            "CARLOS MENDOZA RODRIGUEZ", "Carlos A. Mendoza"
        ).replace(
            "carlos.mendoza@corporativo.com", "c.mendoza@gmail.com"
        ).replace(
            "+52 55 1234 5678", "55-1234-5678"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(variant_content)
            temp_file_path = temp_file.name
        
        try:
            with open(temp_file_path, 'rb') as f:
                files = {
                    'file': ('carlos_mendoza_variant.docx', f.read(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                }
                
                headers = {'Authorization': f'Bearer {self.token}'}
                
                response = requests.post(
                    f"{self.base_url}/api/candidates/upload-resume",
                    files=files,
                    headers=headers,
                    timeout=90
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    status = result.get('status')
                    duplicates = result.get('duplicates', [])
                    
                    if status == 'duplicate_detected' and duplicates:
                        max_confidence = max(d.get('confidence', 0) for d in duplicates)
                        
                        success = max_confidence >= 0.90
                        
                        self.log_test(
                            "Duplicate Detection Accuracy",
                            success,
                            f"Status: {status}, Duplicates: {len(duplicates)}, Max confidence: {max_confidence:.2f}",
                            critical=True
                        )
                        return success
                    else:
                        # Check if it was processed as new candidate with low confidence duplicates
                        has_low_confidence = result.get('has_low_confidence_duplicates', False)
                        
                        self.log_test(
                            "Duplicate Detection Accuracy", 
                            False, 
                            f"Status: {status}, Low confidence duplicates: {has_low_confidence}. Expected high confidence duplicate detection.",
                            critical=True
                        )
                        return False
                else:
                    self.log_test("Duplicate Detection Accuracy", False, f"Status: {response.status_code}", critical=True)
                    return False
                    
        except Exception as e:
            self.log_test("Duplicate Detection Accuracy", False, f"Exception: {str(e)}", critical=True)
            return False
        finally:
            try:
                os.unlink(temp_file_path)
            except:
                pass

    def test_object_storage_integration(self):
        """Verify Emergent Object Storage integration"""
        print("\n🔍 Testing Object Storage Integration...")
        
        if not self.candidate_ids:
            self.log_test("Object Storage Integration", False, "No candidates available for testing", critical=True)
            return False
        
        try:
            candidate_id = self.candidate_ids[0]
            response = requests.get(
                f"{self.base_url}/api/candidates/{candidate_id}",
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                candidate = response.json()
                resume_files = candidate.get('resume_files', [])
                
                if resume_files:
                    file_path = resume_files[0].get('file_path', '')
                    
                    # Verify object storage characteristics
                    is_emergent_storage = (
                        'atlas-talent-vault' in file_path and 
                        'resumes' in file_path and
                        not file_path.startswith('/app/') and  # Not local filesystem
                        not file_path.startswith('uploads/') and  # Not local uploads
                        len(file_path.split('/')) >= 3  # Proper path structure
                    )
                    
                    self.log_test(
                        "Object Storage Integration",
                        is_emergent_storage,
                        f"Storage path: {file_path}, Is Emergent: {is_emergent_storage}",
                        critical=True
                    )
                    return is_emergent_storage
                else:
                    self.log_test("Object Storage Integration", False, "No resume files found in candidate", critical=True)
                    return False
            else:
                self.log_test("Object Storage Integration", False, f"Status: {response.status_code}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("Object Storage Integration", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_semantic_search_business_scenarios(self):
        """Test semantic search with real recruiting scenarios"""
        print("\n🔍 Testing Semantic Search for Business Scenarios...")
        
        business_queries = [
            ("CFO manufactura automotriz", "automotive finance executive"),
            ("Director operaciones retail", "retail operations leader"),
            ("Gerente supply chain FMCG", "FMCG supply chain manager"),
            ("VP finanzas con experiencia M&A", "finance VP with M&A experience"),
            ("Director general manufactura", "manufacturing general manager")
        ]
        
        successful_queries = 0
        
        for query, description in business_queries:
            try:
                params = {
                    'query': query,
                    'use_semantic': True,
                    'limit': 20
                }
                
                response = requests.post(
                    f"{self.base_url}/api/search/hybrid",
                    params=params,
                    headers={'Authorization': f'Bearer {self.token}'},
                    timeout=60
                )
                
                if response.status_code == 200:
                    results = response.json()
                    
                    # Analyze result quality
                    relevant_results = []
                    for result in results:
                        match_score = result.get('match_score', 0)
                        semantic_score = result.get('match_breakdown', {}).get('semantic', 0)
                        
                        if match_score > 0 or semantic_score > 0:
                            relevant_results.append(result)
                    
                    # Success criteria: at least some results with semantic matching
                    has_semantic_results = any(
                        r.get('match_breakdown', {}).get('semantic', 0) > 0 
                        for r in results
                    )
                    
                    if len(relevant_results) > 0 and has_semantic_results:
                        successful_queries += 1
                        self.log_test(
                            f"Semantic Search: {description}",
                            True,
                            f"Query: '{query}' → {len(relevant_results)} relevant results"
                        )
                    else:
                        self.log_test(
                            f"Semantic Search: {description}",
                            False,
                            f"Query: '{query}' → No semantic results found"
                        )
                else:
                    self.log_test(
                        f"Semantic Search: {description}",
                        False,
                        f"Query: '{query}' → Status: {response.status_code}"
                    )
                    
            except Exception as e:
                self.log_test(
                    f"Semantic Search: {description}",
                    False,
                    f"Query: '{query}' → Exception: {str(e)}"
                )
        
        # Overall semantic search assessment
        success_rate = successful_queries / len(business_queries)
        overall_success = success_rate >= 0.6  # At least 60% should work
        
        self.log_test(
            "Semantic Search Overall",
            overall_success,
            f"Success rate: {successful_queries}/{len(business_queries)} ({success_rate:.1%})",
            critical=True
        )
        
        return overall_success

    def test_taxonomy_crud_operations(self):
        """Test taxonomy CRUD with super admin"""
        print("\n🔍 Testing Taxonomy CRUD Operations...")
        
        if not self.admin_token:
            self.log_test("Taxonomy CRUD Operations", False, "No super admin token available", critical=True)
            return False
        
        # Test creating industry
        industry_data = {
            "name_es": "Tecnología Emergente",
            "name_en": "Emerging Technology",
            "description": "Industria de tecnologías emergentes para pruebas"
        }
        
        try:
            # CREATE
            response = requests.post(
                f"{self.base_url}/api/admin/industries",
                json=industry_data,
                headers={'Authorization': f'Bearer {self.admin_token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                industry_id = result.get('industry_id')
                
                if industry_id:
                    self.log_test("CRUD: Create Industry", True, f"Created industry: {industry_id}")
                    
                    # UPDATE
                    update_data = {
                        "name_es": "Tecnología Emergente Actualizada",
                        "name_en": "Updated Emerging Technology",
                        "description": "Industria actualizada para pruebas"
                    }
                    
                    update_response = requests.put(
                        f"{self.base_url}/api/admin/industries/{industry_id}",
                        json=update_data,
                        headers={'Authorization': f'Bearer {self.admin_token}'},
                        timeout=30
                    )
                    
                    if update_response.status_code == 200:
                        self.log_test("CRUD: Update Industry", True, "Industry updated successfully")
                        
                        # DELETE
                        delete_response = requests.delete(
                            f"{self.base_url}/api/admin/industries/{industry_id}",
                            headers={'Authorization': f'Bearer {self.admin_token}'},
                            timeout=30
                        )
                        
                        if delete_response.status_code == 200:
                            self.log_test("CRUD: Delete Industry", True, "Industry deleted successfully")
                            
                            # Overall CRUD success
                            self.log_test("Taxonomy CRUD Operations", True, "All CRUD operations successful", critical=True)
                            return True
                        else:
                            self.log_test("CRUD: Delete Industry", False, f"Status: {delete_response.status_code}")
                    else:
                        self.log_test("CRUD: Update Industry", False, f"Status: {update_response.status_code}")
                else:
                    self.log_test("CRUD: Create Industry", False, "No industry_id returned")
            else:
                self.log_test("CRUD: Create Industry", False, f"Status: {response.status_code}")
                
            self.log_test("Taxonomy CRUD Operations", False, "One or more CRUD operations failed", critical=True)
            return False
                
        except Exception as e:
            self.log_test("Taxonomy CRUD Operations", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_system_performance(self):
        """Test system performance with multiple operations"""
        print("\n🔍 Testing System Performance...")
        
        profiles = [
            ("cfo", "CFO Profile"),
            ("operations_director", "Operations Director Profile")
        ]
        
        upload_times = []
        search_times = []
        successful_operations = 0
        total_operations = 0
        
        for profile_type, description in profiles:
            # Test upload performance
            start_time = time.time()
            
            cv_content = self.create_realistic_pdf_content(profile_type)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(cv_content)
                temp_file_path = temp_file.name
            
            try:
                with open(temp_file_path, 'rb') as f:
                    files = {
                        'file': (f'performance_test_{profile_type}.pdf', f.read(), 'application/pdf')
                    }
                    
                    response = requests.post(
                        f"{self.base_url}/api/candidates/upload-resume",
                        files=files,
                        headers={'Authorization': f'Bearer {self.token}'},
                        timeout=120
                    )
                    
                    upload_time = time.time() - start_time
                    upload_times.append(upload_time)
                    total_operations += 1
                    
                    if response.status_code == 200:
                        successful_operations += 1
                        result = response.json()
                        if result.get('candidate_id'):
                            self.candidate_ids.append(result['candidate_id'])
                    
                    self.log_test(
                        f"Performance: Upload {description}",
                        response.status_code == 200,
                        f"Time: {upload_time:.2f}s, Status: {response.status_code}"
                    )
                    
            except Exception as e:
                self.log_test(f"Performance: Upload {description}", False, f"Exception: {str(e)}")
                total_operations += 1
            finally:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
            # Test search performance
            search_start = time.time()
            try:
                params = {
                    'query': f'{profile_type} executive',
                    'use_semantic': True,
                    'limit': 10
                }
                
                search_response = requests.post(
                    f"{self.base_url}/api/search/hybrid",
                    params=params,
                    headers={'Authorization': f'Bearer {self.token}'},
                    timeout=60
                )
                
                search_time = time.time() - search_start
                search_times.append(search_time)
                total_operations += 1
                
                if search_response.status_code == 200:
                    successful_operations += 1
                
                self.log_test(
                    f"Performance: Search {description}",
                    search_response.status_code == 200,
                    f"Time: {search_time:.2f}s, Status: {search_response.status_code}"
                )
                
            except Exception as e:
                self.log_test(f"Performance: Search {description}", False, f"Exception: {str(e)}")
                total_operations += 1
        
        # Performance analysis
        if upload_times and search_times:
            avg_upload = sum(upload_times) / len(upload_times)
            avg_search = sum(search_times) / len(search_times)
            max_upload = max(upload_times)
            max_search = max(search_times)
            success_rate = successful_operations / total_operations
            
            # Performance criteria
            upload_acceptable = avg_upload < 45 and max_upload < 90  # Reasonable for AI processing
            search_acceptable = avg_search < 10 and max_search < 20   # Search should be fast
            success_acceptable = success_rate >= 0.8
            
            overall_performance = upload_acceptable and search_acceptable and success_acceptable
            
            self.log_test(
                "System Performance Analysis",
                overall_performance,
                f"Upload avg: {avg_upload:.1f}s (max: {max_upload:.1f}s), Search avg: {avg_search:.1f}s (max: {max_search:.1f}s), Success: {success_rate:.1%}",
                critical=True
            )
            
            return overall_performance
        
        return False

    def run_comprehensive_validation(self):
        """Run comprehensive validation for Phase 2 readiness"""
        print("🚀 ATLAS TALENT VAULT - PHASE 2 READINESS VALIDATION")
        print("=" * 70)
        
        # Setup
        print("\n🔧 SETUP PHASE")
        print("-" * 30)
        
        if not self.authenticate():
            print("\n❌ Authentication failed - cannot proceed")
            return False
        
        self.create_super_admin_user()  # Try to create super admin
        
        # Core validation tests
        print("\n🎯 CORE VALIDATION TESTS")
        print("-" * 30)
        
        self.test_real_cv_upload_flow()
        self.test_duplicate_detection_accuracy()
        self.test_object_storage_integration()
        self.test_semantic_search_business_scenarios()
        self.test_taxonomy_crud_operations()
        self.test_system_performance()
        
        return True

    def print_phase2_readiness_report(self):
        """Print Phase 2 readiness assessment"""
        print("\n" + "=" * 70)
        print("📋 PHASE 2 READINESS ASSESSMENT")
        print("=" * 70)
        
        critical_tests = [r for r in self.test_results if r.get('critical', False)]
        critical_passed = [r for r in critical_tests if r['success']]
        
        print(f"Total Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Overall Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        print(f"\nCritical Business Features: {len(critical_tests)}")
        print(f"Critical Features Working: {len(critical_passed)}")
        print(f"Critical Success Rate: {(len(critical_passed) / len(critical_tests) * 100):.1f}%" if critical_tests else "N/A")
        
        # Detailed assessment
        failed_critical = [r for r in critical_tests if not r['success']]
        
        if failed_critical:
            print(f"\n❌ CRITICAL ISSUES BLOCKING PHASE 2:")
            for result in failed_critical:
                print(f"  • {result['test']}: {result['details']}")
        
        # Phase 2 readiness decision
        critical_success_rate = len(critical_passed) / len(critical_tests) if critical_tests else 0
        overall_success_rate = self.tests_passed / self.tests_run if self.tests_run > 0 else 0
        
        # Criteria for Phase 2 readiness
        ready_for_phase2 = (
            critical_success_rate >= 0.8 and  # 80% of critical features working
            overall_success_rate >= 0.7 and   # 70% overall success
            len(self.candidate_ids) > 0        # At least one successful upload
        )
        
        print(f"\n{'🎉 SYSTEM READY FOR PHASE 2' if ready_for_phase2 else '⚠️  SYSTEM NEEDS FIXES BEFORE PHASE 2'}")
        
        if ready_for_phase2:
            print("✅ Core AI features working")
            print("✅ Object storage integrated")
            print("✅ Search functionality operational")
            print("✅ Performance within acceptable limits")
        else:
            print("❌ Critical features need attention")
            print("❌ System not ready for internal team use")
        
        return ready_for_phase2

def main():
    tester = AtlasRealWorldTester()
    
    try:
        success = tester.run_comprehensive_validation()
        ready_for_phase2 = tester.print_phase2_readiness_report()
        
        # Save comprehensive results
        with open('/app/phase2_readiness_report.json', 'w') as f:
            json.dump({
                'phase2_ready': ready_for_phase2,
                'summary': {
                    'total_tests': tester.tests_run,
                    'passed_tests': tester.tests_passed,
                    'failed_tests': tester.tests_run - tester.tests_passed,
                    'success_rate': tester.tests_passed / tester.tests_run * 100 if tester.tests_run > 0 else 0,
                    'critical_features_working': len([r for r in tester.test_results if r.get('critical', False) and r['success']]),
                    'critical_features_total': len([r for r in tester.test_results if r.get('critical', False)])
                },
                'detailed_results': tester.test_results,
                'candidate_ids_created': tester.candidate_ids,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        return 0 if ready_for_phase2 else 1
        
    except Exception as e:
        print(f"\n💥 Validation failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())