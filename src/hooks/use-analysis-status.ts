import { useEffect } from "react"
import { getAnalysisStatus } from "@/lib/api"
import { useDatasetStore } from "@/stores/dataset-store"


export function useAnalysisStatus(sessionId?: string) {

const updateDatasetStatus =
useDatasetStore(
(state)=>state.updateDatasetStatus
)


useEffect(()=>{

if(!sessionId)
 return


const interval=setInterval(async()=>{

try{

const result = await getAnalysisStatus(sessionId)


updateDatasetStatus(
sessionId,
result.status === "completed"
? "Analyzed"
: "Processing"
)


if(result.status==="completed"){
clearInterval(interval)
}


}catch(err){
console.error(err)
}


},3000)


    return () => clearInterval(interval)
  }, [sessionId, updateDatasetStatus])
}