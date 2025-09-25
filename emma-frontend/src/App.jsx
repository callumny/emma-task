import React, { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export default function App() {
  const [text, setText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  async function analyze() {
    setLoading(true)
    const resp = await fetch(`${API_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    const data = await resp.json()
    setResult(data)
    setLoading(false)
  }

  return (
    <div style={{ padding: '1rem', fontFamily: 'sans-serif' }}>
      <h2>Incident Analyzer</h2>
      <textarea
        rows={8}
        style={{ width: '100%' }}
        value={text}
        onChange={e => setText(e.target.value)}
      />
      <br />
      <button onClick={analyze} disabled={loading}>
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>

      {result && (
        <div style={{ marginTop: '1rem' }}>
          <h3>Extraction Source: {result.extraction_source}</h3>
          <h4>Incident Form</h4>
          <pre>{JSON.stringify(result.incident_form, null, 2)}</pre>
          <h4>Draft Email</h4>
          <pre>{result.draft_email}</pre>
          <h4>Evidence</h4>
          <pre>{JSON.stringify(result.evidence, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
