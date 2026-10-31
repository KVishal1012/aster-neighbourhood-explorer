/** Browsers may already decode Content-Encoding:gzip; static hosts may serve raw .gz bytes. */
export async function decodeJsonResponse(response:Response):Promise<unknown>{
 const bytes=new Uint8Array(await response.arrayBuffer());
 if(bytes.length===0)throw new Error('Empty snapshot response');
 const raw=bytes[0]===0x1f&&bytes[1]===0x8b;
 const text=raw?await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text():new TextDecoder().decode(bytes);
 return JSON.parse(text);
}
