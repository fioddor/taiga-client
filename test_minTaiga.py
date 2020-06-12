#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Fioddor Superconcentrado
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#
# Purpose: Automatic tests for TaigaClient.
#
# Design.: - Unittest as framework.
#          - More and better tests:
#            - Wrong token in more calls.
#            - Mocked unit tests.
#            - Corrected tests.
#          - Based on min_taiga.11.py:
#            - Checks for specific TaigaClient exceptions. This
#              unveiled some test errors. Tests were corrected.
#
# Authors:
#     Igor Zubiaurre <fioddor@gmail.com>
#
# Pending:
#   - Complete mocked tests:
#     - proj cases
#   - Integrate into perceval structure.
#   - More TCs:
#     - Throttle responses: HTTP 429
#       { "_error_message": "Request was throttled.Expected available in 279 seconds."
#       , "_error_type": "taiga.base.exceptions.Throttled"
#       }
#     - Expired token => HTTP 301?
#   - Generalise Exceptions and other client-specific objects?
#   - readfile shold be shared with gitlab (remove when integrating and ask for it to be moved).
#----------------------------------------------------------------------------------------------------------------------

import unittest                       # common usage.
import configparser                   # for TestTaigaClientAgainstRealServer.
import httpretty as mock, os , json   # for TestTaigaClientAgainstMockServer.

# for common usage:
from min_taiga import TaigaMinClient as TaigaClient
from min_taiga import *


CFG_FILE = 'test_minTaiga.cfg'



class TestTaigaClientAgainstRealServer(unittest.TestCase):
    """Integration testing.

    Purpose: Integration
             + Regression test the server with the client.
             + Real fire tests to detect unacurate mocking.
    Usage..: 1) Update credentials and token in CFG_FILE (taiga_site.cfg).
             2) Update test data as needed.
             3) Run.
    Design.: + Test data are read from a config file.
             + Setup creates a default client to be reused.
             + Real Taiga projects are expected to grow. Obviously, we don't have control over
               them, andthus, failures might be false positives.
    """
     
    
    @classmethod
    def setUpClass(cls):
        '''Set up tests.'''
        
        # clean up common test data:
        cls.API_URL = None
        cls.API_USR = None
        cls.API_PWD = None
        cls.API_TKN = None
        cls.TST_CFG = None
        cls.TST_DTC = None
         
        # read config file:
        cfg = Utilities.read_test_config( CFG_FILE )
        
         
        # take url:
        if cfg['url']:
            cls.API_URL = cfg['url']
        else:
            raise Exception( 'Missing url in {}.'.format( CFG_FILE ) )
        
        # take credentials (2 options):
        
        has_usr_pwd = cfg['usr'] and cfg['pwd']
        if has_usr_pwd:
            cls.API_USR = cfg['usr']
            cls.API_PWD = cfg['pwd']
            # print( 'Debug: TestTaigaClient.setup_taiga has read user {}, pswd {}.'.format( cls.API_USR , cls.API_PWD ) )
         
        has_token = cfg['tkn']
        if has_token:
            cls.API_TKN = cfg['tkn']
             # print( 'Debug: TestTaigaClient.setup_taiga has read token {}.'.format( cls.API_TKN ) )
         
        if not (has_usr_pwd or hastoken):
            raise Exception('TestTaigaClient.setup_taiga FAILED due to test data missing: credentials missing in test config file.')
         
        # load other test data:
        cls.TST_CFG = cfg['cfg']
        if has_token:
            cls.TST_DTC = TaigaClient( url=cls.API_URL , token=cls.API_TKN )
     
     
    def test_init_with_user_and_pswd(self):
        '''A pswd-born client is created without token.
        
        Design: - Data used in client init doesn't affect this requirement. This testcase inits it
                  with valid data (checked in other testcases). A similar testcase tests this with
                  invalid data.
                - This test doesn't actually call to a real server, but it is in this class because
                  it uses valid data. Thar data is proven valid through real calls in other tests
                  of this class.
        '''
        tmc = TaigaClient( url=self.API_URL , user=self.API_USR , pswd=self.API_PWD )
        self.assertEqual( None , tmc.get_token() )
         
         
    def test_initialization(self):
        '''Test Taiga Client initializations.'''
         
        SAFE_API_COMMAND = 'projects'
         
        # user&pswd init(implicit url, user, pswd) executes (no exception): 
        tmc = TaigaClient( self.API_URL , self.API_USR , self.API_PWD )
         
        # a fresh user&pswd init sets no token:
        self.assertEqual( None , tmc.get_token() )
         
        # ... thus, it raises exception if executed before login():
        with self.assertRaises( Uninitiated_TaigaClient ):
            tmc.basic_rq(SAFE_API_COMMAND)
         
        # ... but after login it executes a request (no exception):
        tmc.login()
        rs1 = tmc.basic_rq(SAFE_API_COMMAND)
         
        self.assertEqual( 200 , rs1.status_code )
        
        # API returns max 30 items per page: (get limit from response header?)
        lst = rs1.json()
        self.assertEqual( 30 , len(lst) )
         
        # ... now it has a (non-None) token:
        fresh_token = tmc.get_token()
        self.assertFalse( None == fresh_token )
        # ... a brand new one:
        self.assertNotEqual( self.API_TKN , fresh_token )
         
        # a token re-init (url, explicit token) executes (no exception):
        tmc = TaigaClient( url=self.API_URL , token=self.API_TKN )
        # its token has changed as requested in the init command:
        self.assertEqual( self.API_TKN , tmc.get_token() )
        # and executes (the same valid) request (no exception):
        rs2 = tmc.basic_rq(SAFE_API_COMMAND)
        self.assertEqual( 200 , rs2.status_code )
         
         
    def test_wrong_token(self):
        '''Taiga rejects wrong tokens.
         
        Taiga's response to a wrong token causes exception in rq() but not in basic_rq().
        '''
        SAFE_API_COMMAND = 'projects'
        EXPECTED_RS_JSON = {"_error_message": "Invalid token", "_error_type": "taiga.base.exceptions.NotAuthenticated"} 
         
        tmc = TaigaClient( url=self.API_URL , token='wrong_token' )
        
        response = tmc.basic_rq( SAFE_API_COMMAND )         
        self.assertEqual( 401 , response.status_code )
        self.assertDictEqual( EXPECTED_RS_JSON , response.json() )
        
        with self.assertRaises( Exception ):
            response = tmc.rq( SAFE_API_COMMAND )
    
    
    def test_pj_stats(self):
        '''Taiga Project Stats'''
         
        def td( var_name ):
            return self.TST_CFG.get( 'test-data' , var_name )
         
        record = self.TST_DTC.proj_stats( td( 'proj_stats_id' ) )
         
        field_names = [ 'total_milestones' , 'defined_points' , 'assigned_points' , 'closed_points' ]
        for field in field_names:
             self.assertGreaterEqual( record[field] , float(td( 'proj_stats_min_'+field )) )
     
     
    def test_pj_issues_stats(self):
        '''Taiga Project Issues Stats'''
         
        def td( var_name ):
            return self.TST_CFG.get( 'test-data' , var_name )
         
        record = self.TST_DTC.proj_issues_stats( td( 'proj_issues_stats_id' ) )
        field_names = [ 'total_issues' , 'opened_issues' , 'closed_issues' ]
        for field in field_names:
            self.assertGreaterEqual( record[field] , float(td( 'proj_issues_stats_min_'+field )) )
         
        group_names = [ 'priority' , 'severity' , 'status' ]
        for group in group_names:
            self.assertGreaterEqual( len(record['issues_per_'+group]) , float(td( 'proj_issues_stats_min_per_'+group )) )
         
         
    def __test_pj_list__(self, list_name):
        '''Standard test for Taiga project list-property'''
         
        def td( var_name ):
            return self.TST_CFG.get( 'test-data' , var_name )
         
        project_id = td( 'proj_{}_id'.format( list_name ) )
        json_list = self.TST_DTC.rq( '{}?project={}'.format( list_name , project_id ) )
        #print( response.headers )
        #json_list = response.json()
        item_count = len(json_list)
        print( '{} {} items found.'.format( item_count , list_name ) )
        # print( 'RS:'+str(json_list) )
         
        min_name = 'proj_{}_min'.format( list_name )
        self.assertGreaterEqual( item_count , float(td( min_name )) )
     
     
    def test_pj_epics(self):
        '''Taiga Project Epics.'''
        return self.__test_pj_list__( 'epics' )
     
     
    def test_pj_userstories(self):
        '''Taiga Project User Stories.'''
        return self.__test_pj_list__( 'userstories' )
     
     
    def test_pj_tasks(self):
        '''Taiga Project Tasks.'''
        return self.__test_pj_list__( 'tasks' )
     
     
    def test_pj_wiki_pages(self):
        '''Taiga Project Wiki Pages.'''
        return self.__test_pj_list__( 'wiki' )
     
     
    def OFF_test_proj_export(self):
        '''Taiga export doesn't work due to permissions.'''
         
        tmc = TaigaClient( url=self.API_URL , token=self.API_TKN )
         
        response = tmc.basic_rq('exporter/156665')
         
        if 403 != response.status_code:
            print(response.json)
        self.assertEqual( 403 , response.status_code )
        self.assertEqual( 'You do not have permission to perform this action.' , response.json()['_error_message'] )
         
          
    def test_proj(self):
        '''Taiga Project data.
        
        Pending: Improve assert.
        '''
        
        data = self.TST_DTC.proj(156665)
         
        print( str(len(    data) ) + ' project data items.' )
        print( str(len(str(data))) + ' bytes of size.'      )
        self.assertTrue(True)



class TestTaigaClientAgainstMockServer(unittest.TestCase):
    """Unit testing.

    Usage..: 0) Install httpretty.
             1) Run.
    Design.: + Taiga API client tested against a mock Taiga server.
             + Setup creates a default client to be reused.
    Pending: - Complete pending test_cases. 
    """
    
    @classmethod
    def setUpClass(cls):
        '''Set up Taiga service'''
        
        cls.API_URL = 'https://a.taiga.instance/API/V9/'
        cls.API_TKN = 'a_clumsy_token'
        # Default Taiga Client for testing.
        cls.TST_DTC = TaigaClient( url=cls.API_URL , token=cls.API_TKN )
    
    
    def test_init_without_expected_arguments_causes_exception(self):
        '''Raises exception if client is requested without expected arguments.
        
        Either:
        a) url and token.
        b) url, user and pswd.
        '''
         
        API_USR = 'a_user'
        API_PWD = 'a_pswd'
        
        # Without arguments at all: 
        self.assertRaises( Missing_Init_Arguments , TaigaClient )
         
        # Only (valid) URL (missing either token or both, user and pswd):
        with self.assertRaises( Missing_Init_Arguments , msg='A TiagaClient init missing token or user or pswd should have raised an Exception.'):
            tmc = TaigaClient( url=self.API_URL ) 
         
        # Missing URL with user and pswd:
        with self.assertRaises( Missing_Init_Arguments , msg='A TaigaClient init missing the url should have raised an Exception.'):
            tmc = TaigaClient( user=API_USR , pswd=API_PWD )

        # Missing URL with a (random) token:
        with self.assertRaises( Missing_Init_Arguments , msg='A TaigaClient init missing the url should have raised an Exception.'):
            tmc = TaigaClient( token='some_clumsy_token' )
         
        # Missing user:
        with self.assertRaises( Missing_Init_Arguments , msg='A TaigaClient init missing the user should have raised an Exception'):
            tmc = TaigaClient( url=self.API_URL , pswd=API_PWD )
         
        # Missing pswd:
        with self.assertRaises( Missing_Init_Arguments , msg='A TaigaClient init missing the pswd should have raised an Exception.'):
            tmc = TaigaClient( url=self.API_URL , user=API_USR )
    
    
    def test_init_with_token(self):
        '''A token-born client...'''
        
        # ...has its token:
        self.assertEqual( self.TST_DTC.get_token() , self.API_TKN )
        
        # ...is born already logged and thus shouldn't login: ")
        with self.assertRaises( Login_Lacks_Credentials ):
            bah = self.TST_DTC.login()
    
    
    def test_init_with_user_and_pswd(self):
        '''A client is created without token.
        
        Client init doesn't immediately connect to API. This would fail later on, at login.
        '''
        
        # a fresh user&pswd client lacks a token yet:
        tmc = TaigaClient( url=self.API_URL , user='a_random_user' , pswd='an_invalid_password' )
        self.assertEqual( None , tmc.get_token() )
        
        # without token nothing works:
        with self.assertRaises( Uninitiated_TaigaClient ):
            bah = tmc.basic_rq(         'should NOT even try')
        with self.assertRaises( Uninitiated_TaigaClient ):
            bah = tmc.rq(               'should NOT even try')
        with self.assertRaises( Uninitiated_TaigaClient ):
            bah = tmc.proj_stats(       'should NOT even try')
        with self.assertRaises( Uninitiated_TaigaClient ):
            bah = tmc.proj_issues_stats('should NOT even try')     
        with self.assertRaises( Uninitiated_TaigaClient ):
            bah = tmc.proj(             'should NOT even try')
        with self.assertRaises( Uninitiated_TaigaClient ):
            bah = tmc.get_lst_data_from_api( 'should NOT even try', [] )
    
    
    @mock.activate
    def test_initialization(self):
        '''Taiga Client initializations.'''
         
        SAFE_API_COMMAND = 'projects'
        mock.register_uri( mock.GET
                         , self.API_URL + SAFE_API_COMMAND
                         , body=read_file('data/taiga/projects.body.RS')
                         , status=200
                         )
        mock.register_uri( mock.POST
                         , self.API_URL + 'auth'
                         , body='{ "auth_token":"a_token" }'
                         , status=200
                         )

        # user&pswd init(implicit url, user, pswd) executes (no exception): 
        tmc = TaigaClient( self.API_URL , 'a_user' , 'a_password' )
         
        # a fresh user&pswd init sets no token:
        self.assertEqual( None , tmc.get_token() )
         
        # ... thus, it raises exception if executed before login():
        with self.assertRaises( Exception ):
            tmc.rq(SAFE_API_COMMAND)
         
        # ... but after login it executes a request (no exception):
        tmc.login()
        rs1 = tmc.basic_rq(SAFE_API_COMMAND)
         
        self.assertEqual( 200 , rs1.status_code )
        
        # API returns max 30 items per page: (get limit from response header?)
        lst = rs1.json()
        self.assertEqual( 30 , len(lst) )
         
        # ... now it has a (non-None) token:
        fresh_token = tmc.get_token()
        self.assertFalse( None == fresh_token )
        # ... a brand new one:
        self.assertNotEqual( self.API_TKN , fresh_token )
         
        # a token re-init (url, explicit token) executes (no exception):
        tmc = TaigaClient( url=self.API_URL , token=self.API_TKN )
        # its token has changed as requested in the init command:
        self.assertEqual( self.API_TKN , tmc.get_token() )
        # and executes (the same valid) request (no exception):
        rs2 = tmc.basic_rq(SAFE_API_COMMAND)
        self.assertEqual( 200 , rs2.status_code )
    
    
    @mock.activate
    def test_login_fail(self):
        '''Taiga denies permission.'''
        
        mock.register_uri( mock.POST
                         , self.API_URL + 'auth'
                         , status=403
                         , body='''{ "etc":"etc" }'''
                         )
        
        tmc = TaigaClient( self.API_URL , user='a_user' , pswd='a_pswd' )
        with self.assertRaises( Exception ):
            bah = tmc.login()
    
    
    @mock.activate
    def test_no_permission(self):
        '''Taiga denies permission.'''
         
        def mock_url( query ):
            mock.register_uri( mock.GET
                             , self.API_URL + query
                             , status=403
                             , body='''{            "etc":"etc"
                                       , "_error_message":"You do not have permission to perform this action."
                                       }
                                    '''
                             )
            print(query)
        
        for u in [ 'deny' , 'projects/id' , 'projects/id/stats', 'projects/id/issues_stats' ]:
            mock_url( u )
        tc = self.TST_DTC
        
        # AC1: basic_rq() raises no exception:
        response = tc.basic_rq( 'deny' )
        response.status_code=403
        
        # AC1: everything else is paginated and rq() raises Unexpected_HTTPcode:
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.rq( 'deny' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.proj_stats( 'id' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.proj_issues_stats( 'id' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.proj( 'id' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.get_lst_data_from_api( 'projects/id/stats', [] )
    
    
    @mock.activate
    def test_wrong_token(self):
        '''Taiga rejects wrong token.'''
         
        def mock_url( query ):
            mock.register_uri( mock.GET
                             , self.API_URL + query
                             , status=401
                             , body='''{            "etc":"etc"
                                       , "_error_message": "Invalid token"
                                       , "_error_type"   : "taiga.base.exceptions.NotAuthenticated"
                                       }
                                    '''
                             )
            #print(query)
        for u in [ 'deny' , 'projects/id' , 'projects/id/stats', 'projects/id/issues_stats' ]:
            mock_url( u )
        tc = self.TST_DTC
        
        response = tc.basic_rq( 'deny' )              # rq raises no exception
        response.status_code=401
         
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.rq( 'deny' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.proj_stats( 'id' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.proj_issues_stats( 'id' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.proj( 'id' )
        with self.assertRaises( Unexpected_HTTPcode ):
            bah = tc.get_lst_data_from_api( 'projects/id/stats', [] )
    
    
    @mock.activate
    def test_rq_max(self):
        '''Rq stops paginating on user limit.'''
        
        TST_QUERY     = 'tasks?project=01'
        TST_PREFIX    = 'pj01_tasks'         # Prefix of the file names containing the mocked responses.
        TST_AVAILABLE = 3                    # Number of mocked pages available to respond the query.
        TST_PER_PAGE  = 30                   # Items per page in the mocked Taiga service.
        
        # dirty fix:
        print()
        
        TST_URL = self.API_URL + TST_QUERY
        Utilities.mock_pages( TST_PREFIX , TST_URL , TST_AVAILABLE )
        
        # AC1: limit, if limit < available:
        limit = TST_AVAILABLE - 1
        record = self.TST_DTC.rq( TST_QUERY , limit )        
        self.assertEqual( limit * TST_PER_PAGE , len(record) )
        
        # AC2: available, if available =< limit:
        record = self.TST_DTC.rq( TST_QUERY , TST_AVAILABLE + 10 ) 
        self.assertLess(   (TST_AVAILABLE - 1) * TST_PER_PAGE , len(record) )
        self.assertGreaterEqual( TST_AVAILABLE * TST_PER_PAGE , len(record) )
        
        # AC3: available, on missing limit:
        record = self.TST_DTC.rq( TST_QUERY ) 
        self.assertLess(   (TST_AVAILABLE - 1) * TST_PER_PAGE , len(record) )
        self.assertGreaterEqual( TST_AVAILABLE * TST_PER_PAGE , len(record) )           
    
    
    @mock.activate
    def test_pj_stats(self):
        '''proj_stats retrieves the expected elements.
         
        None should be missing. No extra item should be dragged along.
        '''
        
        TST_PROJECT       = 'proj_id'
        TST_EXTRA_ITEM    = 'extra_item'
        TST_RESPONSE_BODY = {    TST_EXTRA_ITEM : 'Do NOT load me!'
                            , 'total_milestones': 111
                            ,   'defined_points': 333
                            ,  'assigned_points': 444
                            ,   'closed_points' : 555
                            ,    'total_points' : 666
                            }
        
        mock.register_uri( mock.GET
                         , '{}projects/{}/stats'.format( self.API_URL , TST_PROJECT )
                         , status=200
                         , body=str(TST_RESPONSE_BODY).replace( "'" , '"' )
                         )
        
        record = self.TST_DTC.proj_stats( TST_PROJECT )
        
        # no expected value is missing:
        expected_field_names = TST_RESPONSE_BODY.keys() - [TST_EXTRA_ITEM]
        for field in expected_field_names:
            self.assertEqual( record[field] , TST_RESPONSE_BODY[field] )
        
        # no unexpected item is present:
        with self.assertRaises( KeyError , msg='TaigaClient.pj_stats is reading unwanted items!'):
            bah = record[TST_EXTRA_ITEM]
    
    
    @mock.activate 
    def test_pj_issues_stats(self):
        '''proj_issues_stats retrieves the expected elements.
        
        None should be missing. No extra item should be dragged along.
        '''
        
        TST_PROJECT       = 'proj_id'
        TST_EXTRA_ITEM    = 'extra_item'
        TST_RESPONSE_BODY = {        TST_EXTRA_ITEM : 'Do NOT load me!'
                            ,        'total_issues' : 55
                            ,       'opened_issues' : 22
                            ,       'closed_issues' : 33
                            , 'issues_per_priority' : ['prio1','prio2','prio3']
                            , 'issues_per_severity' : ['sev1','sev2','sev3','sev4']
                            , 'issues_per_status'   : ['status1','status2']
                            }
        
        mock.register_uri( mock.GET
                         , '{}projects/{}/issues_stats'.format( self.API_URL , TST_PROJECT )
                         , status=200
                         , body=str(TST_RESPONSE_BODY).replace( "'" , '"' )
                         )
        
        record = self.TST_DTC.proj_issues_stats( TST_PROJECT )
        
        field_names = [ 'total_issues' , 'opened_issues' , 'closed_issues' ]
        for field in field_names:
            self.assertEqual( record[field] , TST_RESPONSE_BODY[field] )
        
        group_names = [ 'priority' , 'severity' , 'status' ]
        for group in group_names:
            field = 'issues_per_'+group
            self.assertFalse( set(record[field]) - set(TST_RESPONSE_BODY[field]) )
    
    
    @mock.activate
    def __test_pj_listfield__(self , TST_LIST , TST_PROJECT, TST_EXPECTED):
        '''Standard test for a Taiga Project ListQueries.

        Checks that the listQuery retrieves a multipage list of the expected size.
        '''
        
        def mock_list(url , list_name , page=None):
            mock.register_uri( mock.GET, url
                             ,          status=200
                             ,            body=           read_file('data/taiga/{}.P{}.body.RS'.format(list_name , page))
                             , forcing_headers=json.loads(read_file('data/taiga/{}.P{}.head.RS'.format(list_name , page)).replace( "'" , '"' ))
                             )
        TST_URL     = '{}?project={}'.format( TST_LIST , TST_PROJECT )
        # order is important for httpretty mock?:
        mock_list( self.API_URL + TST_URL + '&page=2' , TST_LIST , 2 )
        mock_list( self.API_URL + TST_URL             , TST_LIST , 1 )
        
        lst = self.TST_DTC.rq( TST_URL )
        
        self.assertEqual( TST_EXPECTED , len(lst) ) 
    
    def test_pj_epics(self):
        '''Taiga Project Epics.'''
        return self.__test_pj_listfield__( 'epics' ,  '353209' , 37 )
    
    def test_pj_userstories(self):
        '''Taiga Project User Stories.'''
        return self.__test_pj_listfield__( 'userstories' , '136141' , 38 )
    
    def test_pj_tasks(self):
        '''Taiga Project Tasks.'''
        return self.__test_pj_listfield__( 'tasks' , '297174' , 38 )
    
    def test_pj_wiki_pages(self):
        '''Taiga Project Wiki Pages.'''
        return self.__test_pj_listfield__( 'wiki' , '361447' , 36 )
    
    
    @mock.activate
    def test_proj(self):
        '''Taiga Project data.'''
        
        def mock_url( list_name , query , project , max_page ):
            name  = 'pj{}_{}'.format(project , list_name )
            url   = self.API_URL + query.format( project )
            Utilities.mock_pages( name , url , max_page )
        
        #                     item ,  url                       , (P ,exp) , (P ,exp)
        STEPS = ( (       'basics' , 'projects/{}'              , (1 , 76) , (1 , 76) )
                , (        'stats' , 'projects/{}/stats'        , (1 , 11) , (1 , 11) )
                , ( 'issues_stats' , 'projects/{}/issues_stats' , (1 , 10) , (1 , 10) )
                , (        'epics' ,       'epics?project={}'   , (1 ,  1) , (1 ,  1) )
                , (  'userstories' , 'userstories?project={}'   , (1 , 29) , (2 , 38) )
                , (        'tasks' ,       'tasks?project={}'   , (3 , 81) , (1 ,  7) )
                , (         'wiki' ,        'wiki?project={}'   , (1 ,  2) , (1 ,  0) )
                )
        TST_PROJECTS = ('01' , '02')
        
        # dirty fix:
        print()
        
        pn = 0
        for project in TST_PROJECTS:
            pn += 1
            
            for s in STEPS:
                item = s[0]
                url  = s[1]
                page = s[1+pn][0]

                mock_url( item , url , project , page )
                        
            data = self.TST_DTC.proj( project )
            
            """
            print( str(len(data)) + ' project data items.' )
            for name in data.keys():
                print( str(len(data[name])) + 'x ' + name )
            print( str(len(str(data))) + ' bytes of size.' )
            # print( str(data) )
            """
            
            for s in STEPS:
                item     = s[0]
                expected = s[1+pn][1]
                item_size = len(data[item])
                
                self.assertEqual( expected , item_size )



class TestsUnderConstruction(unittest.TestCase):
    '''Tests Under Construction.

    Sandbox for new testing aproaches. Spikes and other prototypes are developed first here.
    '''
    
    
    def OFF_test_api_command(self):
        tmc = TaigaClient( url=self.API_URL , token=self.API_TKN )
         
        response1 = tmc.basic_rq('projects?is_backlog_activated=true&is_kanban_activated=true')
        if 200 != response1.status_code:
            print( response1.headers )
            print( response1 )
            self.fail( "Coudn't test projects/id/stats because the request for project list failed." )
            return
        lst = response1.json()
        print( str(len(lst)) + ' projects found.' )
        print( response1.headers )
        print( lst )
        return
        for pj in lst:
            command_under_test = 'wiki?project={}'.format( pj['id'] )
            response = tmc.rq(command_under_test)
             
            if 200==response.status_code:
                rec = response.json()
                num = len(rec)
                if 0 < num:
                    print( str(pj['id']) + ' has ' + str(len(rec)) + ' wiki pages.' )
                    # print(str(rec))
        return
     
     
    def OFF_test_under_construction(self):
        '''This test is under construction.'''
         
        tmc = TaigaClient( url=self.API_URL , token=self.API_TKN )
         
        response = tmc.basic_rq('new API command here')
         
        print( '/--- Rq:' )
        print( response.request.headers )
        print( response.request.body    )
        print( response.headers     )
        print( response.status_code )
        print( response.text[:100] + ' ...' )
        print( response.json )
        print( '\\--- Rq' )



class Utilities(unittest.TestCase):
    ''' Testing Utilities.'''
    
    def read_test_config(config_file):
        '''Read Testing configuration'''
         
        # read config file:
        config = configparser.RawConfigParser()
        config.read( config_file )
         
        # take url:
        try:
            url = config.get( 'taiga-site' , 'API_URL' )
        except KeyError:
            url = None
         
        # take credentials (2 options):
        tag = 'taiga-default-credentials'
         
        try:
            usr = config.get( tag , 'User'     )
            pwd = config.get( tag , 'Password' )
            # print( 'Debug: Utilities.read_test_config has read user {}, pswd {}.'.format( usr , pwd ) )
        except KeyError:
            usr = None
            pwd = None
        
        try:
            tkn = config.get( tag , 'Token' )
            # print( 'Debug: TestTaigaClient.setup_taiga has read token {}.'.format( tkn ) )
        except KeyError:
            tkn = None

         
        # load other test data:
        cfg = config

        return { 'url':url , 'usr':usr , 'pwd':pwd , 'tkn':tkn , 'cfg':cfg }
    
    
    def mock_pages( name , query , max_page ):
        '''Mocks a series of pages.'''
        for p in range( max_page ):
            page = p + 1
            
            url = query
            if 0 < p:
                url += '&page={}'.format( page )
            
            TST_DIR = 'data/taiga/'
            body_file = '{}{}.P{}.body.RS'.format( TST_DIR , name , page )
            head_file = '{}{}.P{}.head.RS'.format( TST_DIR , name , page )
                            
            mock.register_uri( mock.GET , url
                             , match_querystring=True
                             ,            status=200
                             ,              body=           read_file(body_file)
                             ,   forcing_headers=json.loads(read_file(head_file).replace( "'" , '"' ))
                             )
            print( 'Mock set up for {}'.format(url) )
    
    
    def test_capture(self):
        '''Runner for testing utilities.
        
        Usage: adapt and call
        '''
        # self.capture_pj_list_RS( '297174' , 'tasks'     )
        # self.capture_pj_list_RS( '297174' , 'tasks' , 2 )
        # self.capture_pj_list_RS( '361447' , 'wiki'      )
        # self.capture_pj_list_RS( '361447' , 'wiki'  , 2 )
        
        # project 01=156665:
        #self.capture_basic_RS( 'projects/156665'                   , 'data/taiga/dnld/pj01_projects.P1.PART.RS'     )
        #self.capture_basic_RS( 'projects/156665/stats'             , 'data/taiga/dnld/pj01_stats.P1.PART.RS'        )
        #self.capture_basic_RS( 'projects/156665/issues_stats'      , 'data/taiga/dnld/pj01_issues_stats.P1.PART.RS' )
        #self.capture_basic_RS( 'epics?project=156665'              , 'data/taiga/dnld/pj01_epics.P1.PART.RS'        )
        #self.capture_basic_RS( 'userstories?project=156665'        , 'data/taiga/dnld/pj01_userstories.P1.PART.RS'  )
        #self.capture_basic_RS( 'tasks?project=156665'              , 'data/taiga/dnld/pj01_tasks.P1.PART.RS'        )
        #self.capture_basic_RS( 'tasks?project=156665&page=2'       , 'data/taiga/dnld/pj01_tasks.P2.PART.RS'        )
        #self.capture_basic_RS( 'tasks?project=156665&page=3'       , 'data/taiga/dnld/pj01_tasks.P3.PART.RS'        )
        #self.capture_basic_RS( 'wiki?project=156665'               , 'data/taiga/dnld/pj01_wiki.P1.PART.RS'         )

        # project 02=136141
        #self.capture_basic_RS( 'projects/136141'                   , 'data/taiga/dnld/pj02_projects.P1.PART.RS'     )
        #self.capture_basic_RS( 'projects/136141/stats'             , 'data/taiga/dnld/pj02_stats.P1.PART.RS'        )
        #self.capture_basic_RS( 'projects/136141/issues_stats'      , 'data/taiga/dnld/pj02_issues_stats.P1.PART.RS' )
        #self.capture_basic_RS( 'epics?project=136141'              , 'data/taiga/dnld/pj02_epics.P1.PART.RS'        )
        #self.capture_basic_RS( 'userstories?project=136141'        , 'data/taiga/dnld/pj02_userstories.P1.PART.RS'  )
        #self.capture_basic_RS( 'userstories?project=136141&page=2' , 'data/taiga/dnld/pj02_userstories.P2.PART.RS'  )
        #self.capture_basic_RS( 'tasks?project=136141'              , 'data/taiga/dnld/pj02_tasks.P1.PART.RS'        )
        #self.capture_basic_RS( 'wiki?project=136141'               , 'data/taiga/dnld/pj02_wiki.P1.PART.RS'         )
    
     
    def capture_pj_list_RS(self, project_id, list_name, page=None):
        '''Testing maintainance utility to capture http responses.'''

        self.setup_taiga()
        destination = 'data/taiga/dnld/{}.P{}.PART.RS'
        url = '{}?project={}'
        if page:
           url += '&page={}'
           url = url.format( list_name , project_id , page )
           destination = destination.format( list_name , page )
        else:
           url = url.format( list_name , project_id )
           destination = destination.format( list_name , "1" )

        self.capture_basic_RS( url , destination )
     
     
    def capture_basic_RS(self, url , destination):
        '''Testing maintainance utility to capture http responses.
         
        Captures response headers and body in respective files.
        :param: destination: 'PART'-marked path to the file where to save.
           Will create 2 files: HEAD and BODY.
        '''
        config = Utilities.read_test_config( CFG_FILE )
        taiga = TaigaClient( url=config['url'] , token = config['tkn'] )
        response = taiga.basic_rq( url )
        if 200 == response.status_code:
           with open( destination.replace('PART' , 'head') , 'w' ) as fh:
               fh.write( str(response.headers) )
           with open( destination.replace('PART' , 'body') , 'w' ) as fb:
               fb.write( response.text )
        else:
           print( 'FAIL:'          )
           print( response.headers )
           print( response.text    )



def read_file(filename, mode='r'):
    '''Taken from test_gitlab.

    Pending: 1. remove (import instead)  when integrated with perceval.
             2. ask for it to be moved to a common place.
    '''
    with open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content



print( '\n' * 3 )

if __name__ == "__main__":
    print( 'Debug: Executing test_taiga as __main__ (called as ./script.py or as python3 script.py).' )
    print( '-' * 40 )
    unittest.main(verbosity=3)
else:
    print( 'Debug: Executing test_taiga as "{}".'.format(__name__) )
    print( '-' * 40 )

