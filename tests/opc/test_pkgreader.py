# encoding: utf-8

"""
Test suite for opc.pkgreader module
"""

from __future__ import absolute_import, print_function, unicode_literals

import pytest

from mock import call, Mock, patch

from pptx.opc.constants import (
    CONTENT_TYPE as CT, RELATIONSHIP_TARGET_MODE as RTM
)
from pptx.opc.packuri import PackURI
from pptx.opc.phys_pkg import _ZipPkgReader
from pptx.opc.pkgreader import (
    _ContentTypeMap, PackageReader, _SerializedPart, _SerializedRelationship,
    _SerializedRelationshipCollection
)

from .unitdata.types import a_Default, a_Types, an_Override
from ..unitutil import class_mock, initializer_mock, method_mock


class DescribePackageReader(object):

    @pytest.fixture
    def from_xml(self, request):
        return method_mock(request, _ContentTypeMap, 'from_xml')

    @pytest.fixture
    def init(self, request):
        return initializer_mock(request, PackageReader)

    @pytest.fixture
    def _load_serialized_parts(self, request):
        return method_mock(request, PackageReader, '_load_serialized_parts')

    @pytest.fixture
    def PhysPkgReader_(self, request):
        _patch = patch(
            'pptx.opc.pkgreader.PhysPkgReader', spec_set=_ZipPkgReader
        )
        request.addfinalizer(_patch.stop)
        return _patch.start()

    @pytest.fixture
    def _SerializedPart_(self, request):
        return class_mock(request, 'pptx.opc.pkgreader._SerializedPart')

    @pytest.fixture
    def _SerializedRelationshipCollection_(self, request):
        return class_mock(
            request, 'pptx.opc.pkgreader._SerializedRelationshipCollection'
        )

    @pytest.fixture
    def _srels_for(self, request):
        return method_mock(request, PackageReader, '_srels_for')

    @pytest.fixture
    def _walk_phys_parts(self, request):
        return method_mock(request, PackageReader, '_walk_phys_parts')

    def it_can_construct_from_pkg_file(self, init, PhysPkgReader_, from_xml,
                                       _srels_for, _load_serialized_parts):
        # mockery ----------------------
        phys_reader = PhysPkgReader_.return_value
        content_types = from_xml.return_value
        pkg_srels = _srels_for.return_value
        sparts = _load_serialized_parts.return_value
        pkg_file = Mock(name='pkg_file')
        # exercise ---------------------
        pkg_reader = PackageReader.from_file(pkg_file)
        # verify -----------------------
        PhysPkgReader_.assert_called_once_with(pkg_file)
        from_xml.assert_called_once_with(phys_reader.content_types_xml)
        _srels_for.assert_called_once_with(phys_reader, '/')
        _load_serialized_parts.assert_called_once_with(phys_reader, pkg_srels,
                                                       content_types)
        phys_reader.close.assert_called_once_with()
        init.assert_called_once_with(content_types, pkg_srels, sparts)
        assert isinstance(pkg_reader, PackageReader)

    def it_can_iterate_over_the_serialized_parts(self):
        # mockery ----------------------
        partname, content_type, blob = ('part/name.xml', 'app/vnd.type',
                                        '<Part_1/>')
        spart = Mock(name='spart', partname=partname,
                     content_type=content_type, blob=blob)
        pkg_reader = PackageReader(None, None, [spart])
        iter_count = 0
        # exercise ---------------------
        for retval in pkg_reader.iter_sparts():
            iter_count += 1
        # verify -----------------------
        assert retval == (partname, content_type, blob)
        assert iter_count == 1

    def it_can_iterate_over_all_the_srels(self):
        # mockery ----------------------
        pkg_srels = ['srel1', 'srel2']
        sparts = [
            Mock(name='spart1', partname='pn1', srels=['srel3', 'srel4']),
            Mock(name='spart2', partname='pn2', srels=['srel5', 'srel6']),
        ]
        pkg_reader = PackageReader(None, pkg_srels, sparts)
        # exercise ---------------------
        generated_tuples = [t for t in pkg_reader.iter_srels()]
        # verify -----------------------
        expected_tuples = [
            ('/',   'srel1'),
            ('/',   'srel2'),
            ('pn1', 'srel3'),
            ('pn1', 'srel4'),
            ('pn2', 'srel5'),
            ('pn2', 'srel6'),
        ]
        assert generated_tuples == expected_tuples

    def it_can_load_serialized_parts(self, _SerializedPart_, _walk_phys_parts):
        # test data --------------------
        test_data = (
            ('/part/name1.xml', 'app/vnd.type_1', '<Part_1/>', 'srels_1'),
            ('/part/name2.xml', 'app/vnd.type_2', '<Part_2/>', 'srels_2'),
        )
        iter_vals = [(t[0], t[2], t[3]) for t in test_data]
        content_types = dict((t[0], t[1]) for t in test_data)
        # mockery ----------------------
        phys_reader = Mock(name='phys_reader')
        pkg_srels = Mock(name='pkg_srels')
        _walk_phys_parts.return_value = iter_vals
        _SerializedPart_.side_effect = expected_sparts = (
            Mock(name='spart_1'), Mock(name='spart_2')
        )
        # exercise ---------------------
        retval = PackageReader._load_serialized_parts(phys_reader, pkg_srels,
                                                      content_types)
        # verify -----------------------
        expected_calls = [
            call('/part/name1.xml', 'app/vnd.type_1', '<Part_1/>', 'srels_1'),
            call('/part/name2.xml', 'app/vnd.type_2', '<Part_2/>', 'srels_2'),
        ]
        assert _SerializedPart_.call_args_list == expected_calls
        assert retval == expected_sparts

    def it_can_walk_phys_pkg_parts(self, _srels_for):
        # test data --------------------
        # +----------+       +--------+
        # | pkg_rels |-----> | part_1 |
        # +----------+       +--------+
        #      |               |    ^
        #      v               v    |
        #   external         +--------+     +--------+
        #                    | part_2 |---> | part_3 |
        #                    +--------+     +--------+
        partname_1, partname_2, partname_3 = (
            '/part/name1.xml', '/part/name2.xml', '/part/name3.xml'
        )
        part_1_blob, part_2_blob, part_3_blob = (
            '<Part_1/>', '<Part_2/>', '<Part_3/>'
        )
        srels = [
            Mock(name='rId1', is_external=True),
            Mock(name='rId2', is_external=False, target_partname=partname_1),
            Mock(name='rId3', is_external=False, target_partname=partname_2),
            Mock(name='rId4', is_external=False, target_partname=partname_1),
            Mock(name='rId5', is_external=False, target_partname=partname_3),
        ]
        pkg_srels = srels[:2]
        part_1_srels = srels[2:3]
        part_2_srels = srels[3:5]
        part_3_srels = []
        # mockery ----------------------
        phys_reader = Mock(name='phys_reader')
        _srels_for.side_effect = [part_1_srels, part_2_srels, part_3_srels]
        phys_reader.blob_for.side_effect = [
            part_1_blob, part_2_blob, part_3_blob
        ]
        # exercise ---------------------
        generated_tuples = [t for t in PackageReader._walk_phys_parts(
            phys_reader, pkg_srels)]
        # verify -----------------------
        expected_tuples = [
            (partname_1, part_1_blob, part_1_srels),
            (partname_2, part_2_blob, part_2_srels),
            (partname_3, part_3_blob, part_3_srels),
        ]
        assert generated_tuples == expected_tuples

    def it_can_retrieve_srels_for_a_source_uri(
            self, _SerializedRelationshipCollection_):
        # mockery ----------------------
        phys_reader = Mock(name='phys_reader')
        source_uri = Mock(name='source_uri')
        rels_xml = phys_reader.rels_xml_for.return_value
        load_from_xml = _SerializedRelationshipCollection_.load_from_xml
        srels = load_from_xml.return_value
        # exercise ---------------------
        retval = PackageReader._srels_for(phys_reader, source_uri)
        # verify -----------------------
        phys_reader.rels_xml_for.assert_called_once_with(source_uri)
        load_from_xml.assert_called_once_with(source_uri.baseURI, rels_xml)
        assert retval == srels


class Describe_ContentTypeMap(object):

    def it_can_construct_from_ct_item_xml(self, from_xml_fixture):
        content_types_xml, expected_defaults, expected_overrides = (
            from_xml_fixture
        )
        ct_map = _ContentTypeMap.from_xml(content_types_xml)
        assert ct_map._defaults == expected_defaults
        assert ct_map._overrides == expected_overrides

    def it_matches_an_override_on_case_insensitive_partname(
            self, match_override_fixture):
        ct_map, partname, content_type = match_override_fixture
        assert ct_map[partname] == content_type

    def it_falls_back_to_defaults(self):
        ct_map = _ContentTypeMap()
        ct_map._overrides = {PackURI('/part/name1.xml'): 'app/vnd.type1'}
        ct_map._defaults = {'.xml': 'application/xml'}
        assert ct_map[PackURI('/part/name2.xml')] == 'application/xml'

    def it_should_raise_on_partname_not_found(self):
        ct_map = _ContentTypeMap()
        with pytest.raises(KeyError):
            ct_map[PackURI('/!blat/rhumba.1x&')]

    def it_should_raise_on_key_not_instance_of_PackURI(self):
        ct_map = _ContentTypeMap()
        ct_map._overrides = {PackURI('/part/name1.xml'): 'app/vnd.type1'}
        with pytest.raises(KeyError):
            ct_map['/part/name1.xml']

    # fixtures ---------------------------------------------

    @pytest.fixture
    def from_xml_fixture(self):
        entries = (
            ('Default', 'xml', CT.XML),
            ('Default', 'PNG', CT.PNG),
            ('Override', '/ppt/presentation.xml', CT.PML_PRESENTATION_MAIN),
        )
        content_types_xml = self._xml_from(entries)
        expected_defaults = {}
        expected_overrides = {}
        for entry in entries:
            if entry[0] == 'Default':
                ext = ('.%s' % entry[1]).lower()
                content_type = entry[2]
                expected_defaults[ext] = content_type
            elif entry[0] == 'Override':
                partname, content_type = entry[1:]
                expected_overrides[partname] = content_type
        return content_types_xml, expected_defaults, expected_overrides

    @pytest.fixture(params=[
        ('/foo/bar.xml', '/foo/bar.xml'),
        ('/foo/bar.xml', '/FOO/Bar.XML'),
        ('/FoO/bAr.XmL', '/foo/bar.xml'),
    ])
    def match_override_fixture(self, request):
        partname_str, should_match_partname_str = request.param
        partname = PackURI(partname_str)
        should_match_partname = PackURI(should_match_partname_str)
        content_type = 'appl/vnd-foobar'
        ct_map = _ContentTypeMap()
        ct_map._add_override(partname, content_type)
        return ct_map, should_match_partname, content_type

    def _xml_from(self, entries):
        """
        Return XML for a [Content_Types].xml based on items in *entries*.
        """
        types_bldr = a_Types().with_nsdecls()
        for entry in entries:
            if entry[0] == 'Default':
                ext, content_type = entry[1:]
                default_bldr = a_Default()
                default_bldr.with_Extension(ext)
                default_bldr.with_ContentType(content_type)
                types_bldr.with_child(default_bldr)
            elif entry[0] == 'Override':
                partname, content_type = entry[1:]
                override_bldr = an_Override()
                override_bldr.with_PartName(partname)
                override_bldr.with_ContentType(content_type)
                types_bldr.with_child(override_bldr)
        return types_bldr.xml()


class Describe_SerializedPart(object):

    def it_remembers_construction_values(self):
        # test data --------------------
        partname = '/part/name.xml'
        content_type = 'app/vnd.type'
        blob = '<Part/>'
        srels = 'srels proxy'
        # exercise ---------------------
        spart = _SerializedPart(partname, content_type, blob, srels)
        # verify -----------------------
        assert spart.partname == partname
        assert spart.content_type == content_type
        assert spart.blob == blob
        assert spart.srels == srels


class Describe_SerializedRelationship(object):

    def it_remembers_construction_values(self):
        # test data --------------------
        rel_elm = Mock(
            name='rel_elm', rId='rId9', reltype='ReLtYpE',
            target_ref='docProps/core.xml', target_mode=RTM.INTERNAL
        )
        # exercise ---------------------
        srel = _SerializedRelationship('/', rel_elm)
        # verify -----------------------
        assert srel.rId == 'rId9'
        assert srel.reltype == 'ReLtYpE'
        assert srel.target_ref == 'docProps/core.xml'
        assert srel.target_mode == RTM.INTERNAL

    def it_knows_when_it_is_external(self):
        cases = (RTM.INTERNAL, RTM.EXTERNAL, 'FOOBAR')
        expected_values = (False, True, False)
        for target_mode, expected_value in zip(cases, expected_values):
            rel_elm = Mock(name='rel_elm', rId=None, reltype=None,
                           target_ref=None, target_mode=target_mode)
            srel = _SerializedRelationship(None, rel_elm)
            assert srel.is_external is expected_value

    def it_can_calculate_its_target_partname(self):
        # test data --------------------
        cases = (
            ('/', 'docProps/core.xml', '/docProps/core.xml'),
            ('/ppt', 'viewProps.xml', '/ppt/viewProps.xml'),
            ('/ppt/slides', '../slideLayouts/slideLayout1.xml',
             '/ppt/slideLayouts/slideLayout1.xml'),
        )
        for baseURI, target_ref, expected_partname in cases:
            # setup --------------------
            rel_elm = Mock(name='rel_elm', rId=None, reltype=None,
                           target_ref=target_ref, target_mode=RTM.INTERNAL)
            # exercise -----------------
            srel = _SerializedRelationship(baseURI, rel_elm)
            # verify -------------------
            assert srel.target_partname == expected_partname

    def it_raises_on_target_partname_when_external(self):
        rel_elm = Mock(
            name='rel_elm', rId='rId9', reltype='ReLtYpE',
            target_ref='docProps/core.xml', target_mode=RTM.EXTERNAL
        )
        srel = _SerializedRelationship('/', rel_elm)
        with pytest.raises(ValueError):
            srel.target_partname


class Describe_SerializedRelationshipCollection(object):

    @pytest.fixture
    def oxml_fromstring(self, request):
        _patch = patch('pptx.opc.pkgreader.oxml_fromstring')
        request.addfinalizer(_patch.stop)
        return _patch.start()

    @pytest.fixture
    def _SerializedRelationship_(self, request):
        return class_mock(
            request, 'pptx.opc.pkgreader._SerializedRelationship'
        )

    def it_can_load_from_xml(self, oxml_fromstring, _SerializedRelationship_):
        # mockery ----------------------
        baseURI, rels_item_xml, rel_elm_1, rel_elm_2 = (
            Mock(name='baseURI'), Mock(name='rels_item_xml'),
            Mock(name='rel_elm_1'), Mock(name='rel_elm_2'),
        )
        rels_elm = Mock(name='rels_elm', Relationship=[rel_elm_1, rel_elm_2])
        oxml_fromstring.return_value = rels_elm
        # exercise ---------------------
        srels = _SerializedRelationshipCollection.load_from_xml(
            baseURI, rels_item_xml)
        # verify -----------------------
        expected_calls = [
            call(baseURI, rel_elm_1),
            call(baseURI, rel_elm_2),
        ]
        oxml_fromstring.assert_called_once_with(rels_item_xml)
        assert _SerializedRelationship_.call_args_list == expected_calls
        assert isinstance(srels, _SerializedRelationshipCollection)

    def it_should_be_iterable(self):
        srels = _SerializedRelationshipCollection()
        try:
            for x in srels:
                pass
        except TypeError:
            msg = "_SerializedRelationshipCollection object is not iterable"
            pytest.fail(msg)
