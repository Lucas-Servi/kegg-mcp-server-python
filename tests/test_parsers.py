"""Unit tests for KEGG response parsers."""

from kegg_mcp_server.parsers import (
    parse_conv_response,
    parse_ddi_response,
    parse_flat_entry,
    parse_link_response,
    parse_multi_flat,
    parse_tab_list,
)

# ---------------------------------------------------------------------------
# parse_tab_list
# ---------------------------------------------------------------------------


class TestParseTabList:
    def test_basic(self, tab_list_text: str) -> None:
        result = parse_tab_list(tab_list_text)
        assert isinstance(result, dict)
        assert len(result) > 0
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, str)

    def test_empty_string(self) -> None:
        assert parse_tab_list("") == {}

    def test_blank_lines_ignored(self) -> None:
        assert parse_tab_list("\n\n  \n") == {}

    def test_single_column_line(self) -> None:
        result = parse_tab_list("hsa00010\n")
        assert "hsa00010" in result
        assert result["hsa00010"] == ""

    def test_two_column_line(self) -> None:
        result = parse_tab_list("hsa00010\tGlycolysis / Gluconeogenesis\n")
        assert result["hsa00010"] == "Glycolysis / Gluconeogenesis"

    def test_multiple_lines(self) -> None:
        text = "A\tfoo\nB\tbar\nC\tbaz\n"
        result = parse_tab_list(text)
        assert result == {"A": "foo", "B": "bar", "C": "baz"}


# ---------------------------------------------------------------------------
# parse_flat_entry (pathway)
# ---------------------------------------------------------------------------


class TestParseFlatEntryPathway:
    def test_has_entry(self, pathway_text: str) -> None:
        result = parse_flat_entry(pathway_text)
        assert "entry" in result
        assert result["entry"] != ""

    def test_has_name(self, pathway_text: str) -> None:
        result = parse_flat_entry(pathway_text)
        assert "name" in result
        name = result["name"]
        assert isinstance(name, (str, list))
        assert name  # non-empty

    def test_entry_type(self, pathway_text: str) -> None:
        result = parse_flat_entry(pathway_text)
        assert "entry_type" in result

    def test_compound_section_is_dict(self, pathway_text: str) -> None:
        result = parse_flat_entry(pathway_text)
        if "compound" in result:
            assert isinstance(result["compound"], dict)

    def test_gene_section_is_dict(self, pathway_text: str) -> None:
        result = parse_flat_entry(pathway_text)
        if "gene" in result:
            assert isinstance(result["gene"], dict)

    def test_empty_input(self) -> None:
        result = parse_flat_entry("")
        assert result == {}

    def test_entry_only(self) -> None:
        text = "ENTRY       C00001                      Compound\n///"
        result = parse_flat_entry(text)
        assert result["entry"] == "C00001"
        assert result["entry_type"] == "Compound"

    def test_terminator_respected(self) -> None:
        text = (
            "ENTRY       X00001                      Test\n"
            "NAME        TestName\n///\nENTRY       Y00001\n"
        )
        result = parse_flat_entry(text)
        assert result["entry"] == "X00001"
        assert "Y00001" not in str(result)


# ---------------------------------------------------------------------------
# parse_flat_entry (gene)
# ---------------------------------------------------------------------------


class TestParseFlatEntryGene:
    def test_has_entry(self, gene_text: str) -> None:
        result = parse_flat_entry(gene_text)
        assert "entry" in result

    def test_has_name(self, gene_text: str) -> None:
        result = parse_flat_entry(gene_text)
        assert "name" in result

    def test_dblinks_is_dict_of_lists(self, gene_text: str) -> None:
        result = parse_flat_entry(gene_text)
        if "dblinks" in result:
            assert isinstance(result["dblinks"], dict)
            for db, ids in result["dblinks"].items():
                assert isinstance(db, str)
                assert isinstance(ids, list)

    def test_orthology_is_dict(self, gene_text: str) -> None:
        result = parse_flat_entry(gene_text)
        if "orthology" in result:
            assert isinstance(result["orthology"], dict)

    def test_pathway_is_dict(self, gene_text: str) -> None:
        result = parse_flat_entry(gene_text)
        if "pathway" in result:
            assert isinstance(result["pathway"], dict)


# ---------------------------------------------------------------------------
# parse_flat_entry (compound)
# ---------------------------------------------------------------------------


class TestParseFlatEntryCompound:
    def test_has_entry(self, compound_text: str) -> None:
        result = parse_flat_entry(compound_text)
        assert "entry" in result

    def test_has_name(self, compound_text: str) -> None:
        result = parse_flat_entry(compound_text)
        assert "name" in result

    def test_formula(self, compound_text: str) -> None:
        result = parse_flat_entry(compound_text)
        # C00002 = ATP, should have a formula
        if "formula" in result:
            assert isinstance(result["formula"], str)
            assert len(result["formula"]) > 0

    def test_exact_mass_is_float(self, compound_text: str) -> None:
        result = parse_flat_entry(compound_text)
        if "exact_mass" in result:
            assert isinstance(result["exact_mass"], float)

    def test_mol_weight_is_float(self, compound_text: str) -> None:
        result = parse_flat_entry(compound_text)
        if "mol_weight" in result:
            assert isinstance(result["mol_weight"], float)

    def test_name_list_for_multiple_names(self) -> None:
        text = (
            "ENTRY       C00002                      Compound\n"
            "NAME        ATP;\n"
            "            Adenosine 5'-triphosphate\n///"
        )
        result = parse_flat_entry(text)
        name = result["name"]
        # Should be a list since there are two names
        assert isinstance(name, list)
        assert len(name) == 2


# ---------------------------------------------------------------------------
# parse_multi_flat
# ---------------------------------------------------------------------------


class TestParseMultiFlat:
    def test_single_entry(self, compound_text: str) -> None:
        entries = parse_multi_flat(compound_text)
        assert len(entries) == 1
        assert "entry" in entries[0]

    def test_two_entries(self) -> None:
        text = (
            "ENTRY       C00001                      Compound\nNAME        Water\n///\n"
            "ENTRY       C00002                      Compound\nNAME        ATP\n///"
        )
        entries = parse_multi_flat(text)
        assert len(entries) == 2
        entries_by_id = {e["entry"]: e for e in entries}
        assert "C00001" in entries_by_id
        assert "C00002" in entries_by_id

    def test_empty(self) -> None:
        assert parse_multi_flat("") == []


# ---------------------------------------------------------------------------
# parse_link_response
# ---------------------------------------------------------------------------


class TestParseLinkResponse:
    def test_basic(self) -> None:
        text = "hsa:1956\tpath:hsa00010\nhsa:1956\tpath:hsa00020\n"
        pairs = parse_link_response(text)
        assert len(pairs) == 2
        assert pairs[0] == ("hsa:1956", "path:hsa00010")
        assert pairs[1] == ("hsa:1956", "path:hsa00020")

    def test_empty(self) -> None:
        assert parse_link_response("") == []

    def test_blank_lines_ignored(self) -> None:
        text = "A\tB\n\n\nC\tD\n"
        pairs = parse_link_response(text)
        assert len(pairs) == 2


# ---------------------------------------------------------------------------
# parse_conv_response
# ---------------------------------------------------------------------------


class TestParseConvResponse:
    def test_basic(self) -> None:
        text = "hsa:1956\tup:P04049\nhsa:2064\tup:P00533\n"
        result = parse_conv_response(text)
        assert result["hsa:1956"] == ["up:P04049"]
        assert result["hsa:2064"] == ["up:P00533"]

    def test_one_to_many_keeps_every_target(self) -> None:
        """Live `/conv/uniprot/hsa:1956` returns three targets; `dict(pairs)`
        used to keep only the last one (F2YGG7), dropping P00533 and Q504U8."""
        text = "hsa:1956\tup:P00533\nhsa:1956\tup:Q504U8\nhsa:1956\tup:F2YGG7\n"
        result = parse_conv_response(text)
        assert result["hsa:1956"] == ["up:P00533", "up:Q504U8", "up:F2YGG7"]

    def test_empty(self) -> None:
        assert parse_conv_response("") == {}


# ---------------------------------------------------------------------------
# parse_ddi_response
# ---------------------------------------------------------------------------


class TestParseDdiResponse:
    def test_returns_list(self, ddi_text: str) -> None:
        result = parse_ddi_response(ddi_text)
        assert isinstance(result, list)

    def test_interaction_fields(self, ddi_text: str) -> None:
        result = parse_ddi_response(ddi_text)
        for item in result:
            assert "drug1" in item
            assert "drug2" in item
            assert "interaction" in item

    def test_empty(self) -> None:
        assert parse_ddi_response("") == []

    def test_manual_three_col(self) -> None:
        text = "D00001\tD00002\tcontraindicated\n"
        result = parse_ddi_response(text)
        assert len(result) == 1
        assert result[0]["drug1"] == "D00001"
        assert result[0]["drug2"] == "D00002"
        assert result[0]["interaction"] == "contraindicated"


# ---------------------------------------------------------------------------
# Map sections: qualifier-prefixed lines must not collide on the qualifier
# ---------------------------------------------------------------------------


class TestMapSectionQualifiers:
    def test_disease_gene_section_keeps_every_qualified_line(self) -> None:
        """Live H00020: five GENE lines share the '(HNPCC)' qualifier.

        Keying on the first token used to collide them all onto one key,
        dropping MLH1, MSH2, MSH6, TGFBR2 (only the last, MLH3, survived)."""
        text = (
            "ENTRY       H00020                      Disease\n"
            "GENE        (HNPCC) MLH1 [HSA:4292] [KO:K08734]\n"
            "            (HNPCC) MSH2 [HSA:4436] [KO:K08735]\n"
            "            (FAP) APC [HSA:324] [KO:K02085]\n"
            "            DCC [HSA:1630] [KO:K06765]\n"
            "///"
        )
        result = parse_flat_entry(text)
        assert set(result["gene"]) == {"MLH1", "MSH2", "APC", "DCC"}
        assert result["gene"]["MLH1"] == "(HNPCC) [HSA:4292] [KO:K08734]"
        assert result["gene"]["DCC"] == "[HSA:1630] [KO:K06765]"

    def test_ko_genes_section_keyed_by_organism(self) -> None:
        """Live K00844 GENES: one organism per line, no shared qualifier."""
        text = (
            "ENTRY       K00844                      KO\n"
            "GENES       HSA: 3098(HK1) 3099(HK2)\n"
            "            PTR: 450504(HKDC1) 450505(HK1)\n"
            "///"
        )
        result = parse_flat_entry(text)
        assert result["genes"]["HSA:"] == "3098(HK1) 3099(HK2)"
        assert result["genes"]["PTR:"] == "450504(HKDC1) 450505(HK1)"


# ---------------------------------------------------------------------------
# MASS (glycans)
# ---------------------------------------------------------------------------


class TestMassSection:
    def test_glycan_mass_strips_trailing_annotation(self) -> None:
        """Live G00001: MASS carries a trailing '(PP-Dol)' annotation."""
        text = (
            "ENTRY       G00001                      Glycan\n"
            "MASS        203.2 (PP-Dol)\n///"
        )
        result = parse_flat_entry(text)
        assert result["mass"] == 203.2

    def test_unparseable_mass_is_none(self) -> None:
        text = "ENTRY       G99999                      Glycan\nMASS        n/a\n///"
        result = parse_flat_entry(text)
        assert result["mass"] is None


# ---------------------------------------------------------------------------
# REFERENCE: DOI continuations and SEQUENCE must not clobber ref_id
# ---------------------------------------------------------------------------


class TestParseReferences:
    def test_doi_continuation_folds_into_journal(self) -> None:
        """Live K04361: a DOI line continues JOURNAL, with no label of its own."""
        text = (
            "ENTRY       K04361                      KO\n"
            "REFERENCE   PMID:11116146\n"
            "  AUTHORS   Habib AA, Chatterjee S\n"
            "  TITLE     The EGFR engages RIP and NIK\n"
            "  JOURNAL   J Biol Chem 276:8865-74 (2001)\n"
            "            DOI:10.1074/jbc.M008458200\n"
            "  SEQUENCE  [hsa:1956]\n"
            "///"
        )
        result = parse_flat_entry(text)
        ref = result["references"][0]
        assert ref["pmid"] == "11116146"
        assert "DOI:10.1074/jbc.M008458200" in ref["journal"]
        assert ref["sequence"] == "[hsa:1956]"
        assert "ref_id" not in ref

    def test_reference_without_doi_still_keeps_sequence(self) -> None:
        text = (
            "ENTRY       K04361                      KO\n"
            "REFERENCE   PMID:12873986\n"
            "  AUTHORS   Shao H, Cheng HY\n"
            "  TITLE     STAT3 recruitment sites\n"
            "  JOURNAL   Cancer Res 63:3923-30 (2003)\n"
            "  SEQUENCE  [hsa:1956]\n"
            "///"
        )
        result = parse_flat_entry(text)
        ref = result["references"][0]
        assert ref["pmid"] == "12873986"
        assert ref["sequence"] == "[hsa:1956]"

    def test_reference_without_pmid_uses_ref_id(self) -> None:
        text = (
            "ENTRY       X00000                      Test\n"
            "REFERENCE   Some free-text citation\n"
            "///"
        )
        result = parse_flat_entry(text)
        ref = result["references"][0]
        assert ref["ref_id"] == "Some free-text citation"
        assert ref.get("pmid") is None
