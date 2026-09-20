import unittest
from scripts.r6_experiment import validate_rewrite, rewrite_usable, interleave, components, validate_metering_history


class RewriteGuardTests(unittest.TestCase):
    def test_unknown_cost_cannot_be_bypassed_on_resume(self):
        for status in ('succeeded','failed'):
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'Missing previous'):
                validate_metering_history({'k':{'status':status,'capability':'embedding','http_status':200,'usage':{}}})
        with self.assertRaisesRegex(ValueError,'uncertain'):
            validate_metering_history({'k':{'status':'started','capability':'text'}})
        validate_metering_history({'k':{'status':'succeeded','capability':'embedding','http_status':200,'usage':{'cost':0}}})

    def test_preserves_identifiers_and_numbers(self):
        request={'query':'嗯，CPU 在 32 位下 `page_size` 怎么设置呀？','language':'zh'}
        result={'query':'CPU 在 32 位下如何设置 page_size？','needs_clarification':False}
        self.assertEqual(validate_rewrite(result,request),result)
        for query in ('CPU 的 page_size 怎么设置？','CPU 在 64 位下如何设置 page_size？','32 位下的 page_size？'):
            with self.subTest(query=query),self.assertRaises(ValueError):
                validate_rewrite(dict(result,query=query),request)

    def test_preserves_cpp_and_plural_acronyms(self):
        for term in ('C++','APIs','C#'):
            request={'query':f'What are these {term} for?','language':'en'}
            with self.subTest(term=term),self.assertRaisesRegex(ValueError,'missing_literals'):
                validate_rewrite({'query':'What are these for?','needs_clarification':False},request)

    def test_missing_context_cannot_be_fabricated_when_flagged(self):
        request={'query':'Where are these APIs used?','language':'en'}
        self.assertTrue(validate_rewrite(dict(query=request['query'],needs_clarification=True),request)['needs_clarification'])
        with self.assertRaisesRegex(ValueError,'clarification_must_preserve'):
            validate_rewrite(dict(query='Where are graphics APIs used?',needs_clarification=True),request)

    def test_invalid_schema_and_translation_rejected(self):
        request={'query':'What does CPU mean?','language':'en'}
        for value in ({'query':'CPU means what?','needs_clarification':'false'},
                      {'query':'CPU 是什么？','needs_clarification':False},
                      {'query':'CPU version 7?','needs_clarification':False},
                      {'query':'CPU means what?','needs_clarification':False,'answer':'extra'}):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_rewrite(value,request)

    def test_only_successful_unambiguous_rewrites_are_used(self):
        self.assertTrue(rewrite_usable({'status':'succeeded','result':{'query':'a','needs_clarification':False}}))
        self.assertFalse(rewrite_usable({'status':'succeeded','result':{'query':'a','needs_clarification':True}}))
        self.assertFalse(rewrite_usable({'status':'failed','result':{'query':'a','needs_clarification':False}}))

    def test_dual_has_total_budget_and_unique_chunks(self):
        a=[{'id':str(i)} for i in range(20)];b=[{'id':str(i)} for i in range(10,30)]
        result=interleave(a,b,20)
        self.assertEqual(len(result),20);self.assertEqual(len({r['id'] for r in result}),20)
        self.assertEqual(result[:2],[a[0],b[0]])
        self.assertEqual(interleave(a,a,20),a)

    def test_source_components_keep_related_families_together(self):
        queries=[{'family_id':'a','relevance':{'doc1':2}},
                 {'family_id':'b','relevance':{'doc1':2,'doc2':2}},
                 {'family_id':'c','relevance':{'doc2':2}},
                 {'family_id':'d','relevance':{'doc3':2}}]
        c=components(queries)
        self.assertEqual(c['a'],c['c']);self.assertNotEqual(c['a'],c['d'])


if __name__=='__main__':unittest.main()
