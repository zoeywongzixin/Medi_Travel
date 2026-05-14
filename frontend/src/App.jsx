import { useState, useEffect, useMemo } from 'react'
import './App.css'

const RAW_API = import.meta.env.VITE_API_BASE
const API_BASE =
  typeof RAW_API === 'string' && RAW_API.trim()
    ? RAW_API.trim().replace(/\/$/, '')
    : import.meta.env.DEV
      ? 'http://localhost:8000/api/v1'
      : '/api/v1'

const FALLBACK_RATES = {
  USD: 1.0,
  MYR: 4.7,
  IDR: 15500.0,
  SGD: 1.35,
  THB: 36.5,
  VND: 24500.0,
  PHP: 56.0,
}

const UI_STRINGS = {
  'app.title': 'Medical Matching Wizard',
  'app.tagline':
    'Structured matching across specialists, travel, and aid—transparent steps, not random suggestions.',
  'common.loading': 'Loading...',
  'stepper.1': 'Chart',
  'stepper.2': 'Specialist',
  'stepper.3': 'Travel',
  'stepper.4': 'Aid',
  'stepper.5': 'Review',
  'thinking.title': 'How the system decides',
  'thinking.show': 'Show details',
  'thinking.hide': 'Hide details',
  'thinking.signals': 'Signals from your case',
  'thinking.steps': 'What happens under the hood',
  'thinking.sources': 'Data sources',
  'thinking.review_title': 'Decision trail (this journey)',
  'thinking.none': 'Complete a step to see how that stage was decided.',
  'step.1.title': 'Step 1: Patient Information',
  'step.1.upload': 'Upload Medical Chart (PDF/Image)',
  'step.1.origin': 'Your Country',
  'step.1.condition': 'Medical Condition',
  'step.1.button': 'Find Specialists',
  'step.2.title': 'Step 2: Select a Doctor',
  'step.2.profile': 'View Profile',
  'step.2.button': 'Find Flights',
  'step.3.title': 'Step 3: Flight Options',
  'step.3.button': 'Find Financial Aid',
  'step.4.title': 'Step 4: Financial Aid / Charity',
  'step.4.button': 'Review Package',
  'step.5.title': 'Step 5: Final Review',
  'step.5.summary_title': 'Message for Hospital (Copy & Send):',
  'step.5.generate': 'Generate Visa/Support Letter',
  'currency.select': 'Currency:',
  'step.2.5.title': 'Help us refine your options',
  'step.2.5.label': 'Why are you dissatisfied?',
  'step.2.5.button': 'Search Again',
  'step.2.5.back': 'Back',
  'step.2.5.placeholder': 'e.g., Too expensive, prefer private hospital, etc.',
  'step.2.refine': 'Dissatisfied with these options?',
  'badge.score': 'Match score',
  'badge.tier': 'Tier',
  'badge.semantic': 'Search rank',
  'badge.source': 'Source',
}

function ThinkingPanel({ data, expanded, onToggle, labels }) {
  if (!data) return null
  const steps =
    data.algorithm_steps ||
    (data.steps || []).map((s) => (typeof s === 'string' ? s : `${s.label}: ${s.detail}`))
  const sources = data.data_sources || []
  const signals = data.case_signals || data.inputs || null

  return (
    <aside className="thinking-aside" aria-label={labels['thinking.title']}>
      <div className="thinking-panel">
        <h3>{data.title || labels['thinking.title']}</h3>
        {data.subtitle && <p className="thinking-sub">{data.subtitle}</p>}
        <button type="button" className="thinking-toggle" onClick={onToggle}>
          <span>{expanded ? labels['thinking.hide'] : labels['thinking.show']}</span>
          <span aria-hidden="true">{expanded ? '▾' : '▸'}</span>
        </button>
        {expanded && (
          <>
            {signals && Object.keys(signals).length > 0 && (
              <>
                <div className="thinking-section-title">{labels['thinking.signals']}</div>
                <div className="thinking-kv">
                  {Object.entries(signals).map(([k, v]) =>
                    v == null || v === '' ? null : (
                      <div key={k}>
                        <span>{k.replace(/_/g, ' ')}: </span>
                        {Array.isArray(v) ? v.join(', ') : String(v)}
                      </div>
                    )
                  )}
                </div>
              </>
            )}
            {data.engine_note && (
              <>
                <div className="thinking-section-title">Logistics</div>
                <p className="thinking-sub" style={{ marginTop: 0 }}>
                  {data.engine_note}
                </p>
              </>
            )}
            {data.option_sources?.length > 0 && (
              <>
                <div className="thinking-section-title">{labels['badge.source']}</div>
                <div className="signal-chips">
                  {data.option_sources.map((s) => (
                    <span key={s} className="signal-chip muted">
                      {s}
                    </span>
                  ))}
                </div>
              </>
            )}
            {steps.length > 0 && (
              <>
                <div className="thinking-section-title">{labels['thinking.steps']}</div>
                <ol className="thinking-list">
                  {steps.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ol>
              </>
            )}
            {sources.length > 0 && (
              <>
                <div className="thinking-section-title">{labels['thinking.sources']}</div>
                <ul className="thinking-list">
                  {sources.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

function getTransparencyForStep(step, transparency) {
  if (step === 1) return transparency.extract
  if (step === 2 || step === 2.5) return transparency.hospitals
  if (step === 3) return transparency.flights
  if (step === 4) return transparency.charities
  return null
}

function App() {
  const [lang, setLang] = useState('en')
  const [t, setT] = useState(UI_STRINGS)

  const [step, setStep] = useState(1)
  const [currency, setCurrency] = useState('USD')

  const [originCountry, setOriginCountry] = useState('Indonesia')
  const [condition, setCondition] = useState('')
  const [medicalData, setMedicalData] = useState({})

  const [doctors, setDoctors] = useState([])
  const [selectedDoctor, setSelectedDoctor] = useState(null)

  const [flights, setFlights] = useState([])
  const [selectedFlight, setSelectedFlight] = useState(null)

  const [charities, setCharities] = useState([])
  const [selectedCharity, setSelectedCharity] = useState(null)

  const [loading, setLoading] = useState(false)
  const [doctorProfileLinks, setDoctorProfileLinks] = useState({})
  const [summaryMsg, setSummaryMsg] = useState('')

  const [dissatisfactionReason, setDissatisfactionReason] = useState('')

  const [transparency, setTransparency] = useState({
    extract: null,
    hospitals: null,
    flights: null,
    charities: null,
  })
  const [thinkingExpanded, setThinkingExpanded] = useState(true)

  const stepperIndex = step === 2.5 ? 2 : step

  const currentThinking = useMemo(
    () => getTransparencyForStep(step, transparency),
    [step, transparency]
  )

  useEffect(() => {
    if (lang === 'en') {
      setT(UI_STRINGS)
      return
    }
    const fetchTranslations = async () => {
      try {
        const res = await fetch(`${API_BASE}/translate-batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ texts: UI_STRINGS, target_language: lang }),
        })
        const data = await res.json()
        if (data.translated_texts) {
          setT((prev) => ({ ...UI_STRINGS, ...data.translated_texts }))
        }
      } catch (e) {
        console.error('Translation error', e)
      }
    }
    fetchTranslations()
  }, [lang])

  const convertPrice = (usd) => {
    if (!usd) return 0
    const rate = FALLBACK_RATES[currency] || 1
    return (parseFloat(usd) * rate).toLocaleString(undefined, { maximumFractionDigits: 0 })
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/extract`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      const extractedCondition =
        data.medical_data?.condition || data.medical_data?.diagnosis || 'Unknown Condition'
      setCondition(extractedCondition)
      setMedicalData(data.medical_data || { condition: extractedCondition })
      setTransparency((prev) => ({ ...prev, extract: data.decision_transparency || null }))
    } catch (err) {
      console.error(err)
      alert('Failed to extract condition from file.')
    }
    setLoading(false)
  }

  const handleFindDoctors = async () => {
    if (!condition) return
    setLoading(true)
    try {
      const payload_md = { ...medicalData, condition }
      const res = await fetch(`${API_BASE}/match-hospitals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          medical_data: payload_md,
          origin_country: originCountry,
          language: lang,
        }),
      })
      const data = await res.json()
      setDoctors(data.hospitals || [])
      setTransparency((prev) => ({ ...prev, hospitals: data.decision_transparency || null }))
      setStep(2)
    } catch (e) {
      console.error(e)
      setDoctors([
        { name: 'Dr. Ahmad bin Ali', hospital: 'Hospital Kuala Lumpur', specialty_tags: 'Cardiology' },
      ])
      setTransparency((prev) => ({ ...prev, hospitals: null }))
      setStep(2)
    }
    setLoading(false)
  }

  const handleRefineDoctors = async () => {
    setLoading(true)
    try {
      const payload_md = { ...medicalData, condition, dissatisfaction_reason: dissatisfactionReason }
      const res = await fetch(`${API_BASE}/match-hospitals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          medical_data: payload_md,
          origin_country: originCountry,
          language: lang,
        }),
      })
      const data = await res.json()
      setTransparency((prev) => ({ ...prev, hospitals: data.decision_transparency || null }))
      if (data.hospitals && data.hospitals.length > 0) {
        const areSame = JSON.stringify(data.hospitals) === JSON.stringify(doctors)
        if (areSame) {
          alert('No other suitable options found based on your feedback.')
        } else {
          setDoctors(data.hospitals)
          alert('We found new options based on your feedback!')
        }
      } else {
        alert('No other suitable options found. Showing previous options.')
      }
      setStep(2)
    } catch (e) {
      console.error(e)
      setStep(2)
    }
    setLoading(false)
  }

  const handleDoctorProfile = async (doc, e) => {
    e.stopPropagation()
    if (doctorProfileLinks[doc.name]) {
      window.open(doctorProfileLinks[doc.name], '_blank')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/doctor-profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doctor_name: doc.name, hospital_name: doc.hospital }),
      })
      const data = await res.json()
      if (data.profile_url) {
        setDoctorProfileLinks((prev) => ({ ...prev, [doc.name]: data.profile_url }))
        window.open(data.profile_url, '_blank')
      } else {
        const fallbackUrl = `/profile.html?name=${encodeURIComponent(doc.name)}&hospital=${encodeURIComponent(doc.hospital)}`
        window.open(fallbackUrl, '_blank')
      }
    } catch (err) {
      console.error(err)
      const fallbackUrl = `/profile.html?name=${encodeURIComponent(doc.name)}&hospital=${encodeURIComponent(doc.hospital)}`
      window.open(fallbackUrl, '_blank')
    }
    setLoading(false)
  }

  const handleFindFlights = async () => {
    if (!selectedDoctor) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/match-flights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          medical_data: { condition },
          origin_country: originCountry,
          language: lang,
        }),
      })
      const data = await res.json()
      setTransparency((prev) => ({ ...prev, flights: data.decision_transparency || null }))
      const flightOptions = data.flight_options?.options || data.flight_options || []
      if (flightOptions.length === 0) {
        setFlights([
          {
            airline: 'Mock Airlines',
            travel_cost_usd: 150,
            route: `${originCountry} to KUL`,
            departure: '10:00',
          },
        ])
      } else {
        setFlights(flightOptions)
      }
      setStep(3)
    } catch (e) {
      console.error(e)
      setFlights([
        {
          airline: 'Mock Airlines',
          travel_cost_usd: 150,
          route: `${originCountry} to KUL`,
          departure: '10:00',
        },
      ])
      setTransparency((prev) => ({ ...prev, flights: null }))
      setStep(3)
    }
    setLoading(false)
  }

  const handleFindCharities = async () => {
    if (!selectedFlight) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/match-charities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          medical_data: { condition },
          origin_country: originCountry,
          language: lang,
        }),
      })
      const data = await res.json()
      setCharities(data.charities || [])
      setTransparency((prev) => ({ ...prev, charities: data.decision_transparency || null }))
      setStep(4)
    } catch (e) {
      console.error(e)
      setCharities([{ name: 'Hope Foundation', max_coverage_usd: 500 }])
      setTransparency((prev) => ({ ...prev, charities: null }))
      setStep(4)
    }
    setLoading(false)
  }

  const generateSummary = async () => {
    const rawMsg = `Hello ${selectedDoctor?.hospital}, I am a patient from ${originCountry}. I am seeking treatment for ${condition}. I would like to consult with ${selectedDoctor?.name}. I will be arriving via ${selectedFlight?.airline}. Please advise on the next steps.`
    if (lang === 'en') {
      setSummaryMsg(rawMsg)
      setStep(5)
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/translate-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: rawMsg, target_language: lang }),
      })
      const data = await res.json()
      setSummaryMsg(data.translated_text || rawMsg)
    } catch (e) {
      setSummaryMsg(rawMsg)
    }
    setStep(5)
    setLoading(false)
  }

  const handleGenerateLetter = async (templateKey = 'mhtc_visa_support') => {
    setLoading(true)
    try {
      const payload_charity = selectedCharity === 'NONE' ? null : selectedCharity
      const res = await fetch(`${API_BASE}/generate-letter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_key: templateKey,
          user_data: { patient_name: 'Patient', current_date: new Date().toLocaleDateString() },
          medical_data: { condition },
          package_data: {
            specialist: selectedDoctor,
            flight: selectedFlight,
            charity: payload_charity,
          },
          target_language: lang,
        }),
      })
      if (res.ok) {
        const blob = await res.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${templateKey}_${lang}.pdf`
        a.click()
      } else {
        alert('Backend failed to generate letter. Check terminal for error.')
      }
    } catch (e) {
      console.error(e)
      alert('Failed to generate letter')
    }
    setLoading(false)
  }

  const stepperDefs = [
    { n: 1, label: t['stepper.1'] },
    { n: 2, label: t['stepper.2'] },
    { n: 3, label: t['stepper.3'] },
    { n: 4, label: t['stepper.4'] },
    { n: 5, label: t['stepper.5'] },
  ]

  const renderStepper = () => (
    <nav className="stepper" aria-label="Progress">
      {stepperDefs.map((s, idx) => {
        const status =
          stepperIndex > s.n ? 'done' : stepperIndex === s.n ? 'active' : ''
        return (
          <span key={s.n}>
            {idx > 0 && <span className="stepper-sep">/</span>}
            <span className={`stepper-step ${status}`}>
              <span className="stepper-num">{s.n}</span>
              {s.label}
            </span>
          </span>
        )
      })}
    </nav>
  )

  const renderReviewThinking = () => {
    const blocks = [
      transparency.extract,
      transparency.hospitals,
      transparency.flights,
      transparency.charities,
    ].filter(Boolean)
    if (!blocks.length) {
      return <p className="thinking-sub">{t['thinking.none']}</p>
    }
    return blocks.map((b, i) => (
      <div key={i} className="thinking-mini">
        <h4>{b.title}</h4>
        <p>{b.subtitle}</p>
      </div>
    ))
  }

  return (
    <div className="app-container">
      <div className="brand-bar">
        <div className="brand-heading-row">
          <div className="logo-mark" aria-hidden="true">
            M
          </div>
          <div className="brand-text">
            <h1>{t['app.title'] || 'Medical Match'}</h1>
            <p className="brand-tagline">{t['app.tagline']}</p>
          </div>
        </div>
        <header>
          <div className="controls-row">
            <div className="form-group" style={{ margin: 0 }}>
              <label className="sr-only" htmlFor="currency-select">
                {t['currency.select']}
              </label>
              <select
                id="currency-select"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                aria-label={t['currency.select']}
              >
                {Object.keys(FALLBACK_RATES).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="sr-only" htmlFor="lang-select">
                Language
              </label>
              <select
                id="lang-select"
                value={lang}
                onChange={(e) => {
                  const newLang = e.target.value
                  setLang(newLang)
                  const countryMap = {
                    ms: 'Malaysia',
                    id: 'Indonesia',
                    th: 'Thailand',
                    vi: 'Vietnam',
                    fil: 'Philippines',
                    km: 'Cambodia',
                    lo: 'Laos',
                    my: 'Myanmar',
                  }
                  if (countryMap[newLang]) {
                    setOriginCountry(countryMap[newLang])
                  }
                }}
                aria-label="Language"
              >
                <option value="en">English</option>
                <option value="ms">Bahasa Malaysia</option>
                <option value="id">Bahasa Indonesia</option>
                <option value="th">ไทย</option>
                <option value="vi">Tiếng Việt</option>
                <option value="fil">Filipino</option>
                <option value="km">ភាសាខ្មែរ</option>
                <option value="lo">ພາສາລາວ</option>
                <option value="my">မြန်မာဘာသာ</option>
              </select>
            </div>
          </div>
        </header>
      </div>

      {renderStepper()}

      <div className="wizard-layout">
        <div className="wizard-main">
          <div className="wizard-card">
            {loading ? (
              <div className="loading-spinner">
                <div className="spinner" />
                <div>{t['common.loading'] || 'Loading...'}</div>
              </div>
            ) : (
              <>
                {step === 1 && (
                  <div className="step">
                    <h2>{t['step.1.title']}</h2>
                    <div className="form-group">
                      <label htmlFor="origin">{t['step.1.origin']}</label>
                      <input
                        id="origin"
                        type="text"
                        className="input-large"
                        value={originCountry}
                        onChange={(e) => setOriginCountry(e.target.value)}
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="chart">{t['step.1.upload']}</label>
                      <div className="file-upload-wrapper">
                        <button type="button" className="btn-upload">
                          Choose file (PDF or image)
                        </button>
                        <input id="chart" type="file" accept=".pdf,image/*" onChange={handleFileUpload} />
                      </div>
                    </div>
                    <div className="form-group">
                      <label htmlFor="condition">{t['step.1.condition']}</label>
                      <input
                        id="condition"
                        type="text"
                        className="input-large"
                        value={condition}
                        onChange={(e) => setCondition(e.target.value)}
                      />
                    </div>
                    <button className="btn-primary" type="button" onClick={handleFindDoctors} disabled={!condition}>
                      {t['step.1.button']}
                    </button>
                  </div>
                )}

                {step === 2 && (
                  <div className="step">
                    <h2>{t['step.2.title']}</h2>
                    <div className="items-grid">
                      {doctors.map((doc) => (
                        <div
                          key={doc.id || doc.name}
                          role="button"
                          tabIndex={0}
                          className={`item-card ${selectedDoctor === doc ? 'selected' : ''}`}
                          onClick={() => setSelectedDoctor(doc)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              setSelectedDoctor(doc)
                            }
                          }}
                        >
                          <div className="item-info">
                            <h3>{doc.name}</h3>
                            <p>
                              {doc.hospital} • {doc.specialty_tags}
                            </p>
                            <div className="signal-chips">
                              {doc.match_score != null && (
                                <span className="signal-chip">
                                  {t['badge.score']}: {doc.match_score}
                                </span>
                              )}
                              {doc.tier && (
                                <span className="signal-chip muted">
                                  {t['badge.tier']}: {doc.tier}
                                </span>
                              )}
                              {doc.semantic_rank != null && (
                                <span className="signal-chip muted">
                                  {t['badge.semantic']}: #{doc.semantic_rank}
                                </span>
                              )}
                            </div>
                            {doc.reasoning && <div className="card-reasoning">{doc.reasoning}</div>}
                          </div>
                          <button
                            type="button"
                            className="external-link"
                            onClick={(e) => handleDoctorProfile(doc, e)}
                          >
                            {t['step.2.profile']}
                          </button>
                        </div>
                      ))}
                    </div>
                    <button
                      className="btn-primary"
                      type="button"
                      onClick={handleFindFlights}
                      disabled={!selectedDoctor}
                    >
                      {t['step.2.button']}
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => setStep(2.5)}>
                      {t['step.2.refine']}
                    </button>
                  </div>
                )}

                {step === 2.5 && (
                  <div className="step">
                    <h2>{t['step.2.5.title'] || 'Help us refine your options'}</h2>
                    <div className="form-group">
                      <label htmlFor="dissatisfaction">{t['step.2.5.label'] || 'Why are you dissatisfied?'}</label>
                      <input
                        id="dissatisfaction"
                        type="text"
                        className="input-large"
                        value={dissatisfactionReason}
                        onChange={(e) => setDissatisfactionReason(e.target.value)}
                        placeholder={
                          t['step.2.5.placeholder'] || 'e.g., Too expensive, prefer private hospital, etc.'
                        }
                      />
                    </div>
                    <button className="btn-primary" type="button" onClick={handleRefineDoctors}>
                      {t['step.2.5.button'] || 'Search Again'}
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => setStep(2)}>
                      {t['step.2.5.back'] || 'Back'}
                    </button>
                  </div>
                )}

                {step === 3 && (
                  <div className="step">
                    <h2>{t['step.3.title']}</h2>
                    <div className="items-grid">
                      {flights.map((flight, idx) => (
                        <div
                          key={idx}
                          role="button"
                          tabIndex={0}
                          className={`item-card ${selectedFlight === flight ? 'selected' : ''}`}
                          onClick={() => setSelectedFlight(flight)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              setSelectedFlight(flight)
                            }
                          }}
                        >
                          <div className="item-info">
                            <h3>{flight.airline || flight.provider}</h3>
                            <p>
                              {flight.route} • {flight.departure}
                            </p>
                            {flight.source && (
                              <div className="signal-chips">
                                <span className="signal-chip muted">
                                  {t['badge.source']}: {flight.source}
                                </span>
                              </div>
                            )}
                            <span className="price-tag">
                              {currency}{' '}
                              {convertPrice(flight.travel_cost_usd || flight.price || flight.fare)}
                            </span>
                            {flight.reasoning && <div className="card-reasoning">{flight.reasoning}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                    <button
                      className="btn-primary"
                      type="button"
                      onClick={handleFindCharities}
                      disabled={!selectedFlight}
                    >
                      {t['step.3.button']}
                    </button>
                  </div>
                )}

                {step === 4 && (
                  <div className="step">
                    <h2>{t['step.4.title']}</h2>
                    <div className="items-grid">
                      {charities.map((charity) => (
                        <div
                          key={charity.id || charity.name}
                          role="button"
                          tabIndex={0}
                          className={`item-card ${selectedCharity === charity ? 'selected' : ''}`}
                          onClick={() => setSelectedCharity(charity)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              setSelectedCharity(charity)
                            }
                          }}
                        >
                          <div className="item-info">
                            <h3>{charity.name}</h3>
                            <span className="price-tag">
                              Up to {currency} {convertPrice(charity.max_coverage_usd)}
                            </span>
                            {charity.website && charity.website !== '#' && (
                              <a
                                href={charity.website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="external-link"
                                style={{ display: 'inline-block', marginTop: '0.5rem' }}
                                onClick={(e) => e.stopPropagation()}
                              >
                                Visit Website
                              </a>
                            )}
                            {charity.reasoning && <div className="card-reasoning">{charity.reasoning}</div>}
                          </div>
                        </div>
                      ))}
                      <div
                        role="button"
                        tabIndex={0}
                        className={`item-card ${selectedCharity === 'NONE' ? 'selected' : ''}`}
                        onClick={() => setSelectedCharity('NONE')}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setSelectedCharity('NONE')
                          }
                        }}
                      >
                        <div className="item-info">
                          <h3>Skip Financial Aid</h3>
                          <p>I do not need charity assistance.</p>
                        </div>
                      </div>
                    </div>
                    <button className="btn-primary" type="button" onClick={generateSummary} disabled={!selectedCharity}>
                      {t['step.4.button']}
                    </button>
                  </div>
                )}

                {step === 5 && (
                  <div className="step">
                    <h2>{t['step.5.title']}</h2>

                    <div className="items-grid" style={{ marginBottom: '2rem' }}>
                      <div className="item-card selected">
                        <div className="item-info">
                          <h3>{selectedDoctor?.name}</h3>
                          <p>{selectedDoctor?.hospital}</p>
                        </div>
                      </div>
                      <div className="item-card selected">
                        <div className="item-info">
                          <h3>{selectedFlight?.airline}</h3>
                          <p>{selectedFlight?.route}</p>
                        </div>
                      </div>
                      {selectedCharity !== 'NONE' && selectedCharity && (
                        <div className="item-card selected">
                          <div className="item-info">
                            <h3>{selectedCharity.name}</h3>
                            <p>Financial Aid Selected</p>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="form-group">
                      <label htmlFor="summary">{t['step.5.summary_title']}</label>
                      <div id="summary" className="summary-box">
                        {summaryMsg}
                      </div>
                    </div>

                    <div className="final-actions">
                      <button className="btn-primary" type="button" onClick={() => handleGenerateLetter('visa_support')}>
                        Download Visa Letter
                      </button>
                      <button
                        className="btn-primary"
                        type="button"
                        onClick={() => handleGenerateLetter('hospital_letter')}
                      >
                        Download Hospital Letter
                      </button>
                      <button className="btn-primary" type="button" onClick={() => handleGenerateLetter('guidelines')}>
                        Download Guidelines
                      </button>
                    </div>

                    <div className="thinking-summary-step5">
                      <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>{t['thinking.review_title']}</h3>
                      {renderReviewThinking()}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {!loading && step !== 5 && (
          <ThinkingPanel
            data={currentThinking}
            expanded={thinkingExpanded}
            onToggle={() => setThinkingExpanded((v) => !v)}
            labels={t}
          />
        )}
      </div>
    </div>
  )
}

export default App
