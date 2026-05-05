package com.example.llmdataanalyst.feature.chat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ArtifactTableParserTest {
    @Test
    fun parsesColumnsRowsList() {
        val raw = """{"columns":["col1","col2"],"rows":[["a","b"],["c","d"]]}"""
        val result = ArtifactTableParser.parse(raw, "t1", "a1")
        assertNotNull(result.table)
        assertEquals(2, result.table!!.rows.size)
    }

    @Test
    fun parsesColumnsRowsObjects() {
        val raw = """{"columns":["col1","col2"],"rows":[{"col1":"a","col2":"b"},{"col1":"c","col2":"d"}]}"""
        val result = ArtifactTableParser.parse(raw, "t2", "a2")
        assertNotNull(result.table)
        assertEquals("a", result.table!!.rows[0][0])
    }

    @Test
    fun parsesArrayOfObjects() {
        val raw = """[{"col1":"a","col2":"b"},{"col1":"c","col2":"d"}]"""
        val result = ArtifactTableParser.parse(raw, "t3", "a3")
        assertNotNull(result.table)
        assertEquals(listOf("col1", "col2"), result.table!!.columns)
    }

    @Test
    fun parsesKeyValueObject() {
        val raw = """{"name":"Sales","mean":123.4,"std":45.6}"""
        val result = ArtifactTableParser.parse(raw, "t4", "a4")
        assertNotNull(result.table)
        assertEquals(listOf("Параметр", "Значение"), result.table!!.columns)
    }

    @Test
    fun malformedJsonFallsBackToJsonBlock() {
        val raw = """{"bad":"""
        val result = ArtifactTableParser.parse(raw, "t5", "a5")
        assertNotNull(result.jsonFallback)
    }

    @Test
    fun nullValuesBecomeDash() {
        val raw = """{"columns":["a"],"rows":[{"a":null}]}"""
        val result = ArtifactTableParser.parse(raw, "t6", "a6")
        assertNotNull(result.table)
        assertEquals("—", result.table!!.rows.first().first())
    }

    @Test
    fun arrayOfArraysCreatesGeneratedColumns() {
        val raw = """[["a","b"],["c","d"]]"""
        val result = ArtifactTableParser.parse(raw, "t7", "a7")
        assertNotNull(result.table)
        assertTrue(result.table!!.columns.first().startsWith("Column"))
    }
}

