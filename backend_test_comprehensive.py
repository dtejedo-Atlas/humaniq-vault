import requests
import sys
import json
import time
import io
from datetime import datetime
from pathlib import Path

class AtlasComprehensiveTester:
    def __init__(self, base_url="https://atlas-recruiting-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
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

    def authenticate(self):
        """Authenticate with test user"""
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

    def create_test_cv_content(self, profile_type="cfo"):
        """Create realistic CV content for testing"""
        if profile_type == "cfo":
            return """
CARLOS MENDOZA RODRIGUEZ
CFO & Director Financiero
carlos.mendoza@email.com | +52 55 1234 5678 | Ciudad de México, México
LinkedIn: linkedin.com/in/carlosmendoza

RESUMEN PROFESIONAL
Director Financiero con 15+ años de experiencia en manufactura automotriz y bienes de consumo. 
Especialista en transformación financiera, fusiones y adquisiciones, y optimización de costos. 
MBA en Finanzas, CPA certificado.

EXPERIENCIA PROFESIONAL

CFO - GRUPO AUTOMOTRIZ MEXICANO (2020-2024)
• Lideré la transformación financiera de empresa con $2B en ingresos
• Implementé sistemas ERP SAP reduciendo costos operativos 15%
• Dirigí 3 adquisiciones estratégicas por $500M
• Equipo de 45 profesionales financieros

Director de Finanzas - NESTLE MEXICO (2016-2020)
• Responsable P&L de 8 categorías de productos
• Optimización de working capital, mejorando cash flow 25%
• Implementación de centros de servicios compartidos

Gerente Financiero Senior - COCA-COLA FEMSA (2012-2016)
• Análisis financiero y planeación estratégica
• Consolidación financiera de 12 plantas
• Proyectos de automatización y digitalización

EDUCACIÓN
• MBA Finanzas - ITAM (2011)
• CPA - Instituto Mexicano de Contadores Públicos (2010)
• Licenciatura en Contaduría - UNAM (2008)

HABILIDADES
• Liderazgo financiero, SAP, Excel avanzado, Power BI
• Fusiones y adquisiciones, Due diligence
• Transformación digital, Lean Six Sigma
• Inglés avanzado, Francés intermedio
            """
        elif profile_type == "operations_director":
            return """
MARIA ELENA GARCIA LOPEZ
Directora de Operaciones | Supply Chain Expert
maria.garcia@email.com | +52 81 9876 5432 | Monterrey, Nuevo León
LinkedIn: linkedin.com/in/mariagarcia

PERFIL EJECUTIVO
Directora de Operaciones con 12+ años transformando operaciones en retail y manufactura.
Experta en supply chain, lean manufacturing y transformación digital.
Reducción de costos operativos >$50M en carrera profesional.

TRAYECTORIA PROFESIONAL

Directora de Operaciones - LIVERPOOL (2021-2024)
• Optimización de cadena de suministro para 120+ tiendas
• Implementación de WMS reduciendo inventario 20%
• Liderazgo de 200+ colaboradores en logística
• Mejora de KPIs: OTD 98%, Fill Rate 95%

Gerente Supply Chain - CEMEX (2018-2021)
• Gestión de supply chain para región Norte de México
• Optimización de rutas de distribución, ahorro $8M anuales
• Implementación de IoT en flotilla de 500+ camiones
• Certificación ISO 9001 y ISO 14001

Coordinadora de Producción - GRUPO BIMBO (2015-2018)
• Supervisión de 3 plantas de producción
• Implementación de metodologías Lean, mejora 15% eficiencia
• Gestión de inventarios y planeación de demanda

FORMACIÓN ACADÉMICA
• Maestría en Logística - ITESM (2014)
• Ingeniería Industrial - UANL (2012)
• Certificación Six Sigma Black Belt (2019)

COMPETENCIAS CLAVE
• Supply Chain Management, Lean Manufacturing
• SAP, WMS, TMS, Power BI, Excel
• Liderazgo de equipos, Gestión de cambio
• Inglés fluido, Alemán básico
            """
        elif profile_type == "supply_chain_manager":
            return """
ROBERTO SILVA HERNANDEZ
Gerente de Supply Chain | Retail & FMCG
roberto.silva@email.com | +52 33 5555 7777 | Guadalajara, Jalisco
LinkedIn: linkedin.com/in/robertosilva

RESUMEN
Gerente de Supply Chain con 8+ años en retail y bienes de consumo.
Especialista en optimización de inventarios, distribución y procurement.
Track record en reducción de costos y mejora de niveles de servicio.

EXPERIENCIA

Gerente Supply Chain - SORIANA (2020-2024)
• Gestión de supply chain para región Occidente (80 tiendas)
• Optimización de inventarios, reducción 18% stock obsoleto
• Negociación con 150+ proveedores, ahorro $12M
• Implementación de S&OP process

Coordinador de Compras - WALMART MEXICO (2018-2020)
• Procurement de categorías no alimentarias
• Gestión de proveedores internacionales (China, USA)
• Análisis de spend, identificación oportunidades ahorro
• KPI: Cost savings 8% anual

Analista de Demanda - UNILEVER (2016-2018)
• Forecasting para 50+ SKUs
• Colaboración con marketing en lanzamientos
• Reducción de forecast error de 25% a 15%

EDUCACIÓN
• Ingeniería en Logística - UP (2015)
• Diplomado Supply Chain - ITAM (2017)
• Certificación APICS SCOR (2019)

HABILIDADES
• Supply Chain Planning, Procurement, Forecasting
• SAP, Oracle, Advanced Excel, Tableau
• Negociación, Análisis de datos
• Inglés avanzado, Portugués intermedio
            """
        
        return self.create_test_cv_content("cfo")  # Default

    def test_cv_upload_and_parsing(self):
        """Test END-TO-END CV upload flow with real parsing"""
        print("\n🔍 Testing CV Upload & AI Parsing...")
        
        # Test CFO profile
        cv_content = self.create_test_cv_content("cfo")
        
        # Create a mock PDF file (in real scenario, this would be actual PDF bytes)
        files = {
            'file': ('carlos_mendoza_cfo.pdf', cv_content.encode(), 'application/pdf')
        }
        
        headers = {'Authorization': f'Bearer {self.token}'}
        
        try:
            response = requests.post(
                f"{self.base_url}/api/candidates/upload-resume",
                files=files,
                headers=headers,
                timeout=60  # AI parsing can take time
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Verify parsing results
                parsed_data = result.get('parsed_data', {})
                candidate_id = result.get('candidate_id')
                
                if candidate_id:
                    self.candidate_ids.append(candidate_id)
                
                # Check if key fields were extracted
                name_extracted = bool(parsed_data.get('full_name'))
                email_extracted = bool(parsed_data.get('email'))
                company_extracted = bool(parsed_data.get('current_company'))
                title_extracted = bool(parsed_data.get('current_title'))
                
                parsing_score = sum([name_extracted, email_extracted, company_extracted, title_extracted])
                
                self.log_test(
                    "CV Upload & AI Parsing", 
                    parsing_score >= 3,  # At least 3/4 key fields
                    f"Parsed {parsing_score}/4 key fields. Name: {name_extracted}, Email: {email_extracted}, Company: {company_extracted}, Title: {title_extracted}",
                    critical=True
                )
                
                # Test Atlas AI Classification
                if candidate_id:
                    time.sleep(2)  # Allow processing
                    self.test_atlas_classification(candidate_id)
                
                return True
            else:
                self.log_test("CV Upload & AI Parsing", False, f"Status: {response.status_code} - {response.text[:200]}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("CV Upload & AI Parsing", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_atlas_classification(self, candidate_id):
        """Test Atlas AI classification accuracy"""
        try:
            response = requests.post(
                f"{self.base_url}/api/atlas/classify/{candidate_id}",
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=45
            )
            
            if response.status_code == 200:
                classification = response.json()
                
                industry = classification.get('industry')
                functional_area = classification.get('functional_area')
                seniority = classification.get('seniority')
                confidence = classification.get('confidence_score', 0)
                
                # For CFO profile, expect Finance/Accounting area and senior/director/c_level
                expected_areas = ['Finance', 'Accounting', 'Finanzas', 'Contabilidad']
                expected_seniority = ['director', 'c_level', 'vp']
                
                area_correct = any(area.lower() in functional_area.lower() if functional_area else False for area in expected_areas)
                seniority_correct = seniority in expected_seniority if seniority else False
                
                self.log_test(
                    "Atlas AI Classification",
                    area_correct and confidence > 0.7,
                    f"Industry: {industry}, Area: {functional_area}, Seniority: {seniority}, Confidence: {confidence:.2f}",
                    critical=True
                )
                
                return True
            else:
                self.log_test("Atlas AI Classification", False, f"Status: {response.status_code}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("Atlas AI Classification", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_duplicate_detection(self):
        """Test duplicate detection with ≥90% confidence"""
        print("\n🔍 Testing Duplicate Detection...")
        
        # Upload same candidate with slight variation
        cv_content_variant = self.create_test_cv_content("cfo").replace("CARLOS MENDOZA RODRIGUEZ", "Carlos Mendoza R.")
        
        files = {
            'file': ('carlos_mendoza_variant.docx', cv_content_variant.encode(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        }
        
        headers = {'Authorization': f'Bearer {self.token}'}
        
        try:
            response = requests.post(
                f"{self.base_url}/api/candidates/upload-resume",
                files=files,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Check if duplicate was detected
                status = result.get('status')
                duplicates = result.get('duplicates', [])
                
                if status == 'duplicate_detected' and duplicates:
                    max_confidence = max(d.get('confidence', 0) for d in duplicates)
                    
                    self.log_test(
                        "Duplicate Detection",
                        max_confidence >= 0.90,
                        f"Detected {len(duplicates)} duplicates, max confidence: {max_confidence:.2f}",
                        critical=True
                    )
                    return True
                else:
                    self.log_test("Duplicate Detection", False, "No duplicates detected or confidence too low", critical=True)
                    return False
            else:
                self.log_test("Duplicate Detection", False, f"Status: {response.status_code}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("Duplicate Detection", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_object_storage_verification(self):
        """Verify CVs are stored in Emergent Object Storage, not local filesystem"""
        print("\n🔍 Testing Object Storage...")
        
        if not self.candidate_ids:
            self.log_test("Object Storage Verification", False, "No candidates to check", critical=True)
            return False
        
        try:
            # Get candidate details to check storage path
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
                    
                    # Check if path indicates object storage (not local filesystem)
                    is_object_storage = (
                        'atlas-talent-vault' in file_path and 
                        'resumes' in file_path and
                        not file_path.startswith('/') and  # Not local path
                        not file_path.startswith('uploads/')  # Not local uploads
                    )
                    
                    self.log_test(
                        "Object Storage Verification",
                        is_object_storage,
                        f"File path: {file_path}",
                        critical=True
                    )
                    return is_object_storage
                else:
                    self.log_test("Object Storage Verification", False, "No resume files found", critical=True)
                    return False
            else:
                self.log_test("Object Storage Verification", False, f"Status: {response.status_code}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("Object Storage Verification", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_hybrid_search_semantic(self):
        """Test hybrid search with realistic recruiting queries"""
        print("\n🔍 Testing Hybrid Search with Semantic Queries...")
        
        test_queries = [
            "CFO manufactura",
            "Director operaciones automotriz", 
            "gerente supply chain retail",
            "Director financiero con experiencia en M&A",
            "Gerente de operaciones con lean manufacturing"
        ]
        
        passed_queries = 0
        
        for query in test_queries:
            try:
                params = {
                    'query': query,
                    'use_semantic': True,
                    'limit': 10
                }
                
                response = requests.post(
                    f"{self.base_url}/api/search/hybrid",
                    params=params,
                    headers={'Authorization': f'Bearer {self.token}'},
                    timeout=45
                )
                
                if response.status_code == 200:
                    results = response.json()
                    
                    # Check if results are relevant (have match scores and proper structure)
                    relevant_results = [
                        r for r in results 
                        if r.get('match_score', 0) > 0 or r.get('match_breakdown')
                    ]
                    
                    if len(relevant_results) > 0:
                        passed_queries += 1
                        self.log_test(
                            f"Semantic Search: '{query}'",
                            True,
                            f"Found {len(relevant_results)} relevant results"
                        )
                    else:
                        self.log_test(
                            f"Semantic Search: '{query}'",
                            False,
                            f"No relevant results found"
                        )
                else:
                    self.log_test(
                        f"Semantic Search: '{query}'",
                        False,
                        f"Status: {response.status_code}"
                    )
                    
            except Exception as e:
                self.log_test(
                    f"Semantic Search: '{query}'",
                    False,
                    f"Exception: {str(e)}"
                )
        
        # Overall semantic search success
        success_rate = passed_queries / len(test_queries)
        self.log_test(
            "Hybrid Search Overall",
            success_rate >= 0.6,  # At least 60% of queries should work
            f"Passed {passed_queries}/{len(test_queries)} queries ({success_rate:.1%})",
            critical=True
        )
        
        return success_rate >= 0.6

    def test_taxonomy_crud(self):
        """Test taxonomy CRUD operations (super_admin required)"""
        print("\n🔍 Testing Taxonomy CRUD...")
        
        # Test creating industry
        industry_data = {
            "name_es": "Industria de Prueba",
            "name_en": "Test Industry",
            "description": "Industria creada para pruebas automatizadas"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/admin/industries",
                json=industry_data,
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                industry_id = result.get('industry_id')
                
                if industry_id:
                    self.log_test("Create Industry", True, f"Created industry: {industry_id}")
                    
                    # Test updating industry
                    update_data = {
                        "name_es": "Industria de Prueba Actualizada",
                        "name_en": "Updated Test Industry",
                        "description": "Industria actualizada"
                    }
                    
                    update_response = requests.put(
                        f"{self.base_url}/api/admin/industries/{industry_id}",
                        json=update_data,
                        headers={'Authorization': f'Bearer {self.token}'},
                        timeout=30
                    )
                    
                    if update_response.status_code == 200:
                        self.log_test("Update Industry", True, "Industry updated successfully")
                        
                        # Test deleting industry
                        delete_response = requests.delete(
                            f"{self.base_url}/api/admin/industries/{industry_id}",
                            headers={'Authorization': f'Bearer {self.token}'},
                            timeout=30
                        )
                        
                        if delete_response.status_code == 200:
                            self.log_test("Delete Industry", True, "Industry deleted successfully")
                            return True
                        else:
                            self.log_test("Delete Industry", False, f"Status: {delete_response.status_code}")
                    else:
                        self.log_test("Update Industry", False, f"Status: {update_response.status_code}")
                else:
                    self.log_test("Create Industry", False, "No industry_id returned")
            else:
                # Might fail due to permissions - check if it's a permission issue
                if response.status_code == 403:
                    self.log_test("Taxonomy CRUD", False, "Permission denied - user may not be super_admin", critical=False)
                else:
                    self.log_test("Create Industry", False, f"Status: {response.status_code}", critical=True)
                return False
                
        except Exception as e:
            self.log_test("Taxonomy CRUD", False, f"Exception: {str(e)}", critical=True)
            return False

    def test_performance_multiple_uploads(self):
        """Test performance with multiple candidate uploads"""
        print("\n🔍 Testing Performance with Multiple Uploads...")
        
        profiles = ["cfo", "operations_director", "supply_chain_manager"]
        upload_times = []
        successful_uploads = 0
        
        for i, profile_type in enumerate(profiles):
            start_time = time.time()
            
            cv_content = self.create_test_cv_content(profile_type)
            files = {
                'file': (f'test_candidate_{i+1}.pdf', cv_content.encode(), 'application/pdf')
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/api/candidates/upload-resume",
                    files=files,
                    headers={'Authorization': f'Bearer {self.token}'},
                    timeout=90
                )
                
                end_time = time.time()
                upload_time = end_time - start_time
                upload_times.append(upload_time)
                
                if response.status_code == 200:
                    successful_uploads += 1
                    result = response.json()
                    if result.get('candidate_id'):
                        self.candidate_ids.append(result['candidate_id'])
                
                self.log_test(
                    f"Performance Upload {i+1}",
                    response.status_code == 200,
                    f"Time: {upload_time:.2f}s, Status: {response.status_code}"
                )
                
            except Exception as e:
                self.log_test(f"Performance Upload {i+1}", False, f"Exception: {str(e)}")
        
        # Analyze performance
        if upload_times:
            avg_time = sum(upload_times) / len(upload_times)
            max_time = max(upload_times)
            
            # Performance criteria: average < 30s, max < 60s
            performance_good = avg_time < 30 and max_time < 60
            
            self.log_test(
                "Performance Analysis",
                performance_good,
                f"Avg: {avg_time:.2f}s, Max: {max_time:.2f}s, Success: {successful_uploads}/{len(profiles)}",
                critical=True
            )
            
            return performance_good
        
        return False

    def run_comprehensive_tests(self):
        """Run all comprehensive tests"""
        print("🚀 Starting Atlas Talent Vault COMPREHENSIVE TESTING")
        print("=" * 60)
        
        # Authentication
        if not self.authenticate():
            print("\n❌ Authentication failed - cannot proceed")
            return False
        
        # Core functionality tests
        print("\n📋 CORE FUNCTIONALITY TESTS")
        print("-" * 40)
        
        self.test_cv_upload_and_parsing()
        self.test_duplicate_detection()
        self.test_object_storage_verification()
        self.test_hybrid_search_semantic()
        self.test_taxonomy_crud()
        self.test_performance_multiple_uploads()
        
        return True

    def print_comprehensive_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST SUMMARY")
        print("=" * 60)
        
        critical_tests = [r for r in self.test_results if r.get('critical', False)]
        critical_passed = [r for r in critical_tests if r['success']]
        
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print(f"\nCritical Tests: {len(critical_tests)}")
        print(f"Critical Passed: {len(critical_passed)}")
        print(f"Critical Success Rate: {(len(critical_passed) / len(critical_tests) * 100):.1f}%" if critical_tests else "N/A")
        
        # Show failed critical tests
        failed_critical = [r for r in critical_tests if not r['success']]
        if failed_critical:
            print("\n❌ FAILED CRITICAL TESTS:")
            for result in failed_critical:
                print(f"  - {result['test']}: {result['details']}")
        
        # Show all failed tests
        failed_tests = [r for r in self.test_results if not r['success']]
        if failed_tests and len(failed_tests) > len(failed_critical):
            print("\n❌ ALL FAILED TESTS:")
            for result in failed_tests:
                print(f"  - {result['test']}: {result['details']}")
        
        # Overall assessment
        critical_success_rate = len(critical_passed) / len(critical_tests) if critical_tests else 1
        overall_success = critical_success_rate >= 0.8 and self.tests_passed / self.tests_run >= 0.7
        
        print(f"\n{'🎉 SYSTEM READY FOR PHASE 2' if overall_success else '⚠️  SYSTEM NEEDS FIXES BEFORE PHASE 2'}")
        
        return overall_success

def main():
    tester = AtlasComprehensiveTester()
    
    try:
        success = tester.run_comprehensive_tests()
        overall_success = tester.print_comprehensive_summary()
        
        # Save detailed results
        with open('/app/comprehensive_test_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': tester.tests_run,
                    'passed_tests': tester.tests_passed,
                    'failed_tests': tester.tests_run - tester.tests_passed,
                    'success_rate': tester.tests_passed / tester.tests_run * 100 if tester.tests_run > 0 else 0,
                    'ready_for_phase_2': overall_success
                },
                'detailed_results': tester.test_results,
                'candidate_ids_created': tester.candidate_ids,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        return 0 if overall_success else 1
        
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())