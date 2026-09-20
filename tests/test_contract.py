"""Confronto del contratto OpenAPI con risposte HTTP reali su archivio isolato."""
import json
import re
import unittest
from pathlib import Path
import test_api as api_fixture

SPEC=json.loads((Path(__file__).resolve().parents[1]/'openapi.yaml').read_text(encoding='utf-8'))

def validate(value,schema):
    if '$ref' in schema:
        schema=SPEC['components']['schemas'][schema['$ref'].split('/')[-1]]
    typ=schema.get('type')
    if typ=='object':
        assert isinstance(value,dict), value
        assert all(k in value for k in schema.get('required',[])), value
        for key,child in schema.get('properties',{}).items():
            if key in value:validate(value[key],child)
    elif typ=='array':
        assert isinstance(value,list)
        for item in value:validate(item,schema['items'])
    elif typ=='integer':assert isinstance(value,int) and not isinstance(value,bool)
    elif typ=='string':assert isinstance(value,str)
    if 'enum' in schema:assert value in schema['enum']

class ContractTests(unittest.TestCase):
    def test_internal_references_and_operation_count(self):
        refs=re.findall(r'"\$ref":\s*"([^"]+)"',json.dumps(SPEC))
        for ref in refs:
            node=SPEC
            for part in ref.removeprefix('#/').split('/'):node=node[part]
        self.assertEqual(sum(len(p) for p in SPEC['paths'].values()),12)
        for path,methods in SPEC['paths'].items():
            for operation in methods.values():self.assertIn('responses',operation)
        self.assertNotIn('content',SPEC['paths']['/logout']['post']['responses']['204'])

    def test_documented_success_responses_and_error_schema(self):
        fixture=api_fixture.ApiTests('test_dashboard_and_read_routes')
        fixture.setUp()
        try:
            token=fixture.tokens['admin']
            cases=[('POST','/login',{'email':'admin@sanitasmart.test','password':'Admin123!'}),('GET','/me',None),('GET','/dashboard',None),('GET','/patients',None),('POST','/patients',dict(name='Prova',email='p@example.test',phone='123')),('GET','/appointments',None),('POST','/appointments',dict(patientId=1,doctor='Dott. Test',specialty='Visita',date='2026-10-12',time='10:00')),('PATCH','/appointments/1/cancel',None),('GET','/reports',None),('POST','/reports',dict(patientId=1,date='2026-10-12',type='ECG',outcome='Esempio')),('GET','/availability?doctor=Dott.%20Test&date=2026-10-12',None),('POST','/logout',None)]
            for method,path,payload in cases:
                status,data=fixture.request(method,'/api'+path,payload,token=token)
                key='/appointments/{id}/cancel' if path.endswith('/cancel') else path.split('?')[0]
                operation=SPEC['paths'][key][method.lower()]
                with self.subTest(path=path,status=status):
                    self.assertIn(str(status),operation['responses'])
                    self.assertIn(status,(200,201,204))
                    response=operation['responses'][str(status)]
                    if status==204:self.assertIsNone(data)
                    else:validate(data,response['content']['application/json']['schema'])
            status,data=fixture.request('GET','/api/me',token=token)
            self.assertEqual(status,401)
            validate(data,SPEC['components']['schemas']['Error'])
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
