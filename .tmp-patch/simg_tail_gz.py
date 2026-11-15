import struct,sys,os,gzip
src=sys.argv[1]; dst=sys.argv[2]; seek_blk=int(sys.argv[3])
f=open(src,"rb"); hdr=f.read(28)
magic,maj,minr,fhcsz,chcsz,blksz,total_blks,total_chunks,cksum=struct.unpack("<IHHHHIIII",hdr)
RAW,FILL,DONT=0xCAC1,0xCAC2,0xCAC3
off=fhcsz; out_blk=0
g=gzip.GzipFile(dst,"wb",compresslevel=1)
zeros=bytes(1024*1024)
def emit_zeros(n):
    while n>0:
        w=min(n,len(zeros)); g.write(zeros[:w]); n-=w
while out_blk<total_blks:
    f.seek(off); ct,resv,csz,tsz=struct.unpack("<HHII",f.read(12))
    cend=out_blk+csz
    lo=max(out_blk,seek_blk); hi=cend
    if hi>lo:
        skip=(lo-out_blk)*blksz; take=(hi-lo)*blksz
        if ct==RAW:
            f.seek(off+chcsz+skip); rem=take
            while rem>0:
                b=f.read(min(rem,8*1024*1024)); g.write(b); rem-=len(b)
        else:
            emit_zeros(take)
    out_blk=cend; off+=tsz
g.close()
print("wrote",os.path.getsize(dst))
