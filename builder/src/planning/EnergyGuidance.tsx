import {useState} from 'react';
import {Lightbulb} from 'lucide-react';

export default function EnergyGuidance(){
 const [annual,setAnnual]=useState('');
 const amount=Number(annual);
 const valid=annual.trim()!==''&&Number.isFinite(amount)&&amount>=0&&amount<=1000000;
 const currency=new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD'});
 return <section className="energy-guidance" aria-labelledby="energy-heading">
  <div className="section-title"><h2 id="energy-heading"><Lightbulb size={25}/> Energy before you move</h2></div>
  <p>Understand what you would pay for, and what to ask the landlord or seller.</p>
  <p className="energy-limit">No energy bills or efficiency rating are verified for this address. This checklist is general guidance, not an assessment of the property.</p>
  <div className="energy-columns"><div>
   <h3>Ask for these details</h3>
   <ul>
    <li><strong>Who pays?</strong> Confirm whether electricity, heating, cooling and hot water are included in rent or charged separately.</li>
    <li><strong>What powers the home?</strong> Ask about the heating and hot-water systems, their fuel, and whether your unit has its own meter.</li>
    <li><strong>What did it cost?</strong> Request 12 consecutive months of bills for the same unit, with personal information removed. Check which services and billing dates they cover.</li>
    <li><strong>What evidence is available?</strong> Ask for any energy assessment, its date, and whether it covers this unit or the whole building. Ask about drafts, insulation and recent upgrades.</li>
   </ul>
  </div><details className="energy-calculator"><summary>Work out an average monthly budget</summary>
   <p>Enter the total from 12 months of bills in Canadian dollars. Include only the services you expect to pay for; avoid counting a charge twice.</p>
   <label htmlFor="annual-energy-cost">Annual bill total (CAD)</label>
   <input id="annual-energy-cost" type="number" inputMode="decimal" min="0" max="1000000" step="0.01" value={annual} onChange={e=>setAnnual(e.target.value)} aria-describedby="energy-calculation-note"/>
   <p role="status" className="energy-budget">{valid?`${currency.format(amount/12)} per month on average`:annual!==''?'Enter a total between $0 and $1,000,000.':'Enter an annual total to see a monthly average.'}</p>
   <p id="energy-calculation-note">Your entered annual total ÷ 12. This is a budgeting calculation, not a forecast or a verified bill. Individual months and future costs can differ with weather, occupancy, usage and rates.</p>
   <small>Kept only in this page’s memory. Not saved, sent, or included in shared snapshot links. Changing address clears this input.</small>
  </details></div>
 </section>;
}
