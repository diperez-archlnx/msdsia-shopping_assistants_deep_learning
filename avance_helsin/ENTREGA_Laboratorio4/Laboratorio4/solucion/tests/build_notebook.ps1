# Convierte notebook_src.txt (celdas separadas por "# %%" / "# %% [markdown]") en el .ipynb de Colab.
$dir = Split-Path $PSScriptRoot -Parent
$src = Get-Content "$dir\notebook_src.txt" -Encoding UTF8
$cells = New-Object System.Collections.ArrayList
$script:cur = $null
function Flush {
    if (-not $script:cur) { return }
    $lines = $script:cur.lines
    while ($lines.Count -gt 0 -and $lines[$lines.Count - 1].Trim() -eq '') { $lines.RemoveAt($lines.Count - 1) }
    $arr = @()
    for ($i = 0; $i -lt $lines.Count; $i++) { $arr += $(if ($i -lt $lines.Count - 1) { $lines[$i] + "`n" } else { $lines[$i] }) }
    if ($script:cur.type -eq 'markdown') { [void]$cells.Add([ordered]@{cell_type = 'markdown'; metadata = @{}; source = $arr}) }
    else { [void]$cells.Add([ordered]@{cell_type = 'code'; execution_count = $null; metadata = @{}; outputs = @(); source = $arr}) }
}
foreach ($l in $src) {
    if ($l -eq '# %% [markdown]') { Flush; $script:cur = @{type = 'markdown'; lines = (New-Object System.Collections.Generic.List[string])}; continue }
    if ($l -eq '# %%') { Flush; $script:cur = @{type = 'code'; lines = (New-Object System.Collections.Generic.List[string])}; continue }
    if ($script:cur.type -eq 'markdown') { if ($l -match '^# ?(.*)$') { $l = $Matches[1] } }
    if ($script:cur.lines.Count -eq 0 -and $l.Trim() -eq '') { continue }
    $script:cur.lines.Add($l)
}
Flush
$nb = [ordered]@{
    cells = $cells
    metadata = [ordered]@{accelerator = 'GPU'; colab = @{provenance = @(); gpuType = 'T4'}
        kernelspec = @{display_name = 'Python 3'; language = 'python'; name = 'python3'}; language_info = @{name = 'python'}}
    nbformat = 4; nbformat_minor = 0
}
$out = "$dir\Laboratorio4_Asistente_Voz.ipynb"
[IO.File]::WriteAllText($out, ($nb | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding $false))
"Notebook regenerado: $($cells.Count) celdas -> $out"
