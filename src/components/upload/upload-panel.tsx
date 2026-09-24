'use client'

import { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { FileDropzone } from './file-dropzone'
import { FileCard } from './file-card'
import { UploadButton } from './upload-button'
import { UploadProgress } from './upload-progress'
import { useAnalysisStore } from '@/stores/analysis-store'
import { useDatasetStore } from '@/stores/dataset-store'
import { useNotificationStore } from '@/stores/notification-store'
import { useReportStore } from '@/stores/report-store'
import { useWorkspaceStore } from '@/stores/workspace-store'
import { analyzeData, fetchMyReports, getAnalysisStatus, getDatasetArtifacts, ensureFreshToken } from '@/lib/api'
import { chatHref, datasetHref } from '@/lib/app-links'
import type { AnalysisStatus } from '@/lib/api'

const completedUploadSessions = new Set<string>()

export function UploadPanel() {
  const router = useRouter()
  const addDataset = useDatasetStore((state) => state.addDataset)
  const updateDatasetStatus = useDatasetStore(
    (state) => state.updateDatasetStatus,
  )
  const setDatasetArtifacts = useDatasetStore((state) => state.setDatasetArtifacts)
  const addReport = useReportStore((state) => state.addReport)
  const openDataset = useWorkspaceStore((state) => state.openDataset)

  const startAnalysis = useAnalysisStore((state) => state.startAnalysis)
  const setAnalysisProgress = useAnalysisStore((state) => state.setProgress)
  const setAnalysisStatus = useAnalysisStore((state) => state.setStatus)
  const setAnalysisArtifacts = useAnalysisStore((state) => state.setArtifacts)
  const setAnalysisError = useAnalysisStore((state) => state.setError)
  const resetAnalysisStore = useAnalysisStore((state) => state.resetAnalysis)

  const [file, setFile] = useState<File | null>(null)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'completed' | 'error'>(
    'idle',
  )
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [uploadSessionFileName, setUploadSessionFileName] = useState<
    string | undefined
  >(undefined)
  const uploadSessionRef = useRef<{
    id: string
    fileName: string
  } | null>(null)
  const completionHandledRef = useRef(false)
  const isLocked = status === 'uploading' || status === 'processing'

  const resetUploadState = () => {
    setFile(null)
    setProgress(0)
    setStatus('idle')
    setErrorMessage(undefined)
    setUploadSessionFileName(undefined)
    uploadSessionRef.current = null
    completionHandledRef.current = false
    resetAnalysisStore()
  }

  const handleUpload = async () => {
    if (!file || isLocked) return

    const fileSizeStr = `${(file.size / 1024 / 1024).toFixed(2)} MB`
    setStatus('uploading')
    setProgress(0)
    setErrorMessage(undefined)
    setUploadSessionFileName(file.name)

    try {
      const result = await analyzeData(file, 'Analyze this dataset', (p) => {
        setProgress(p)
        setAnalysisProgress(p)
      })
      const sessionId = result.session_id
      setProgress(100)
      setStatus('processing')
      startAnalysis({
        sessionId,
        fileName: file.name,
        fileSize: fileSizeStr,
        fileType: file.type,
      })
      setAnalysisStatus('processing')

      uploadSessionRef.current = {
        id: sessionId,
        fileName: file.name,
      }

      addDataset({
        id: sessionId,
        name: file.name,
        size: fileSizeStr,
        type: file.type,
        status: 'Processing',
        uploadedAt: new Date().toISOString(),
      })

      openDataset(sessionId)

      // Surface an upload notification so recent activity stays available.
      useNotificationStore.getState().addNotification({
        id: `${sessionId}-upload`,
        action: 'Dataset uploaded',
        file: file.name,
        time: 'Just now',
        href: datasetHref(sessionId),
      })

      let pollStatus: AnalysisStatus

      while (true) {
        pollStatus = await getAnalysisStatus(sessionId)

        if (pollStatus.status === 'completed') {
          const artifacts = await getDatasetArtifacts(sessionId)
          if (artifacts.status !== 'completed') throw new Error('Analysis completed without artifacts')
          setDatasetArtifacts(sessionId, artifacts)
          setAnalysisArtifacts(artifacts)
          break
        }

        if (pollStatus.status === 'failed') {
          throw new Error(pollStatus.error || 'Analysis failed')
        }

        await new Promise((resolve) => setTimeout(resolve, 2500))
      }

      setProgress(100)
      updateDatasetStatus(sessionId, 'Analyzed')

      // The report is persisted by the backend. Re-read it from PostgreSQL so
      // the store uses the real report UUID and dataset session id.
      try {
        await ensureFreshToken()
        const remoteReports = await fetchMyReports()
        const persistedReport = remoteReports.find(
          (report) => report.dataset_id === sessionId,
        )
        if (persistedReport) {
          addReport({
            id: persistedReport.id,
            title: persistedReport.title,
            dataset: persistedReport.dataset || file.name,
            datasetId: persistedReport.dataset_id ?? sessionId,
            type: persistedReport.type || 'AI Analysis',
            date: persistedReport.date || persistedReport.created_at || new Date().toISOString(),
            createdAt: persistedReport.created_at ?? undefined,
          })
        }
      } catch (reportErr) {
        console.warn('Report was generated but could not be reloaded from server:', reportErr)
      }

      useNotificationStore.getState().addNotification({
        id: `${sessionId}-analysis-complete`,
        action: 'Analysis completed',
        file: file.name,
        time: 'Just now',
        href: chatHref(sessionId),
      })

      completedUploadSessions.add(sessionId)
      completionHandledRef.current = true
      setStatus('completed')

      // After analysis finishes, open the chat workspace for this dataset.
      router.push(`/chat?dataset=${encodeURIComponent(sessionId)}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Something went wrong during analysis'
      setErrorMessage(msg)
      setStatus('error')
      setAnalysisError(msg)

      toast.error('Analysis failed', {
        description: msg,
      })

      console.error(err)
    }
  }

  return (
    <div className="mx-auto flex h-full max-h-full w-full max-w-3xl flex-col justify-center gap-2 overflow-y-auto p-3">
      <div className="rounded-xl border border-border bg-card p-4 shadow-xs">
        <FileDropzone
          disabled={isLocked}
          onFileSelected={(selectedFile) => {
            resetUploadState()
            setFile(selectedFile)
          }}
        />
      </div>

      {file && (
        <FileCard
          file={file}
          disableRemove={isLocked}
          variant={status === 'completed' ? 'success' : isError(status) ? 'default' : 'default'}
          onRemove={resetUploadState}
        />
      )}

      {status !== 'completed' && (
        <UploadButton disabled={!file || isLocked} onUpload={handleUpload} />
      )}

      {status !== 'idle' && (
        <UploadProgress
          progress={progress}
          status={status}
          fileName={file?.name ?? uploadSessionFileName}
          errorMessage={errorMessage}
        />
      )}
    </div>
  )
}

function isError(status: string): boolean {
  return status === 'error'
}