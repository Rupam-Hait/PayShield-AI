"""
Engine 8 & Innovation: NetworkX Buyer-Supplier Graph & SVG Generator
Generates server-side NetworkX dependency graph and outputs valid, responsive SVG directly.
Zero JavaScript required.
"""

from typing import Dict, Any, List
import networkx as nx
from sqlalchemy.orm import Session
from models.tenant import Tenant
from models.buyer import Buyer
from models.invoice import Invoice

class NetworkGraphEngine:
    def __init__(self, db_session: Session):
        self.db = db_session

    def generate_buyer_network_svg(self, tenant_id: str, width: int = 800, height: int = 500) -> str:
        """
        Build NetworkX bipartite/dependency graph of MSME -> Buyers -> Invoices,
        and render clean server-side SVG.
        """
        tenant = self.db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            return "<svg><text>Tenant not found</text></svg>"

        buyers = self.db.query(Buyer).filter(Buyer.tenant_id == tenant_id).all()
        invoices = self.db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.status.in_(['ISSUED', 'DELIVERED', 'ACCEPTED', 'PARTIALLY_PAID'])
        ).all()

        G = nx.Graph()
        
        # Center Node: MSME
        msme_node = f"MSME:{tenant.business_name}"
        G.add_node(msme_node, node_type='MSME', label=tenant.business_name[:20], size=28)

        total_outstanding = sum(i.outstanding_amount for i in invoices) or 1.0

        # Buyer Nodes & Edges
        buyer_exposure = {}
        for b in buyers:
            b_invs = [i for i in invoices if i.buyer_id == b.buyer_id]
            b_total = sum(i.outstanding_amount for i in b_invs)
            buyer_exposure[b.buyer_id] = b_total
            
            b_node = f"BUYER:{b.canonical_name}"
            # Concentration ratio
            conc = b_total / total_outstanding
            status = 'HIGH RISK' if conc > 0.35 else ('WATCH' if conc > 0.15 else 'SAFE')
            
            G.add_node(
                b_node,
                node_type='BUYER',
                label=b.canonical_name[:18],
                amount=b_total,
                conc=conc,
                status=status,
                is_cpse=b.is_cpse
            )
            G.add_edge(msme_node, b_node, weight=conc)

            # Invoice leaves
            for inv in b_invs[:4]: # Cap at 4 invoices per buyer for visual clarity
                inv_node = f"INV:{inv.invoice_number}"
                G.add_node(
                    inv_node,
                    node_type='INVOICE',
                    label=inv.invoice_number,
                    amount=inv.outstanding_amount,
                    status=inv.status
                )
                G.add_edge(b_node, inv_node)

        # Layout computation using spring layout
        pos = nx.spring_layout(G, k=0.9, iterations=50, seed=42)

        # Scale layout coordinates to SVG viewBox (padding 60px)
        pad = 60
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        min_x, max_x = min(xs) if xs else -1, max(xs) if xs else 1
        min_y, max_y = min(ys) if ys else -1, max(ys) if ys else 1

        def scale_coord(p):
            sx = pad + (p[0] - min_x) / (max_x - min_x + 1e-5) * (width - 2 * pad)
            sy = pad + (p[1] - min_y) / (max_y - min_y + 1e-5) * (height - 2 * pad)
            return sx, sy

        # Build SVG Elements
        svg_lines = []
        svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" class="ledger-graph-svg">')
        svg_lines.append('<defs>')
        svg_lines.append('<filter id="subtle-shadow" x="-10%" y="-10%" width="120%" height="120%"><feDropShadow dx="1" dy="2" stdDeviation="2" flood-color="#1B2430" flood-opacity="0.15"/></filter>')
        svg_lines.append('</defs>')

        # Draw Edges
        for u, v in G.edges():
            x1, y1 = scale_coord(pos[u])
            x2, y2 = scale_coord(pos[v])
            svg_lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#A0AAB2" stroke-width="1.5" stroke-dasharray="3,3"/>')

        # Draw Nodes
        for node, data in G.nodes(data=True):
            cx, cy = scale_coord(pos[node])
            ntype = data.get('node_type', 'MSME')
            
            if ntype == 'MSME':
                # Center Hub
                svg_lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="32" fill="#2E4057" stroke="#1B2430" stroke-width="2"/>')
                svg_lines.append(f'<text x="{cx:.1f}" y="{cy-4:.1f}" font-family="Source Serif 4, serif" font-size="11" font-weight="bold" fill="#F7F5F0" text-anchor="middle">MSME</text>')
                svg_lines.append(f'<text x="{cx:.1f}" y="{cy+12:.1f}" font-family="Public Sans, sans-serif" font-size="9" fill="#E2E8F0" text-anchor="middle">{data["label"]}</text>')
            elif ntype == 'BUYER':
                status = data.get('status', 'SAFE')
                fill_color = '#2E7D32' if status == 'SAFE' else ('#B78103' if status == 'WATCH' else '#C62828')
                radius = 22 if data.get('is_cpse') else 18
                amt_lakhs = round(data.get('amount', 0) / 100000.0, 1)
                
                svg_lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" fill="#F7F5F0" stroke="{fill_color}" stroke-width="3" filter="url(#subtle-shadow)"/>')
                svg_lines.append(f'<text x="{cx:.1f}" y="{cy-2:.1f}" font-family="Public Sans, sans-serif" font-size="9" font-weight="bold" fill="#1B2430" text-anchor="middle">{data["label"][:10]}</text>')
                svg_lines.append(f'<text x="{cx:.1f}" y="{cy+10:.1f}" font-family="Source Serif 4, serif" font-size="8" fill="{fill_color}" text-anchor="middle">₹{amt_lakhs}L</text>')
            else: # INVOICE leaf
                svg_lines.append(f'<rect x="{cx-24:.1f}" y="{cy-12:.1f}" width="48" height="24" rx="2" fill="#FFFFFF" stroke="#64748B" stroke-width="1"/>')
                svg_lines.append(f'<text x="{cx:.1f}" y="{cy+3:.1f}" font-family="Public Sans, sans-serif" font-size="8" fill="#1B2430" text-anchor="middle">{data["label"]}</text>')

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)
