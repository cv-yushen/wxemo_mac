/*
 * crack_fast.c — fast, param-agnostic WeChat key finder.
 *
 * For every 32-byte window in memory, treat it as an AES-256 key, ECB-decrypt the
 * first ciphertext block p1[16:32] once, then XOR with candidate IVs (reserve
 * 48/64/80 + zero + salt) to reconstruct CBC plaintext block 0, and check the
 * SQLite header (page-size 0x1000 + version bytes). One AES block per candidate.
 * Robust to unknown HMAC/KDF and to the exact reserve size.
 *
 * Build: cc -O2 -o crack_fast crack_fast.c -framework Foundation
 * Run  : sudo WECHAT_ACCT=<your_wxid_prefix> ./crack_fast
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <pwd.h>
#include <ftw.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonCrypto.h>

#define PAGE_SZ 4096
#define SALT_SZ 16
#define KEY_SZ 32
#define CHUNK_SIZE (4*1024*1024)
#define MAX_DBS 128

static char g_db_rel[MAX_DBS][512];
static unsigned char g_db_page1[MAX_DBS][PAGE_SZ];
static char g_db_base[1024];
static int g_db_count = 0;

static int nftw_collect(const char *fpath, const struct stat *sb, int tf, struct FTW *ftw){
    (void)sb;(void)ftw;
    if(tf!=FTW_F)return 0;
    size_t n=strlen(fpath);
    if(n<3||strcmp(fpath+n-3,".db"))return 0;
    FILE *f=fopen(fpath,"rb"); if(!f)return 0;
    unsigned char p1[PAGE_SZ]; size_t got=fread(p1,1,PAGE_SZ,f); fclose(f);
    if(got<PAGE_SZ)return 0;
    if(!memcmp(p1,"SQLite format 3",15))return 0;
    if(g_db_count>=MAX_DBS)return 0;
    const char *rel=fpath+strlen(g_db_base); while(*rel=='/')rel++;
    snprintf(g_db_rel[g_db_count],512,"%s",rel);
    memcpy(g_db_page1[g_db_count],p1,PAGE_SZ);
    g_db_count++; return 0;
}

/* candidate IVs for CBC block-0, per possible reserve size, from target page1 */
static unsigned char g_iv[8][16]; static int g_ivres[8]; static int g_nIV=0;
static const unsigned char *g_p1;    /* target page1 (4096 bytes) */

/* ECB-decrypt one 16-byte block with a 32-byte key */
static inline int aes_ecb_dec_block(const unsigned char *key, const unsigned char *in, unsigned char *out){
    size_t moved=0;
    return CCCrypt(kCCDecrypt,kCCAlgorithmAES,kCCOptionECBMode,key,KEY_SZ,NULL,in,16,out,16,&moved)==kCCSuccess && moved==16;
}

/* Strong confirm: CBC-decrypt first 8 blocks (128B) with key+iv, reconstruct sqlite
 * page1, and require: header[16:18]=4096, wv==rv in {1,2}, reserved-bytes in {32,48,64,80},
 * and page-1 b-tree type at offset 100 in {0x02,0x05,0x0a,0x0d}. */
static int confirm(const unsigned char *key, const unsigned char *iv){
    unsigned char ct[128]; memcpy(ct, g_p1+SALT_SZ, 128);
    unsigned char pt[128];
    size_t moved=0;
    if(CCCrypt(kCCDecrypt,kCCAlgorithmAES,kCCOptionECBMode,key,KEY_SZ,NULL,ct,128,pt,128,&moved)!=kCCSuccess) return 0;
    /* CBC unchaining: pt[0]^=iv ; pt[k]^=ct[k-1] */
    for(int b=0;b<8;b++){ const unsigned char *x = b? ct+(b-1)*16 : iv; for(int j=0;j<16;j++) pt[b*16+j]^=x[j]; }
    /* pt corresponds to file bytes [16:144]; sqlite header fields: */
    if(pt[0]!=0x10||pt[1]!=0x00) return 0;          /* [16:18] page size 4096 */
    int wv=pt[2], rv=pt[3];                           /* [18],[19] */
    if(wv!=rv || (wv!=1&&wv!=2)) return 0;
    int reserved=pt[4];                               /* [20] reserved bytes/page */
    if(reserved!=32&&reserved!=48&&reserved!=64&&reserved!=80) return 0;
    int btype=pt[100-16];                             /* file offset 100 -> pt[84] */
    if(btype!=0x02&&btype!=0x05&&btype!=0x0a&&btype!=0x0d) return 0;
    return reserved;                                  /* return the true reserve size */
}

/* returns IV index+1 if key strongly validates, else 0 */
static int g_reserve_out=0;
static int check_key(const unsigned char *key){
    unsigned char d[16];
    if(!aes_ecb_dec_block(key,g_p1+SALT_SZ,d)) return 0;
    for(int i=0;i<g_nIV;i++){
        /* cheap block-0 gate */
        if((d[0]^g_iv[i][0])!=0x10) continue;
        if((d[1]^g_iv[i][1])!=0x00) continue;
        int wv=d[2]^g_iv[i][2], rv=d[3]^g_iv[i][3];
        if(wv!=rv||(wv!=1&&wv!=2)) continue;
        int r=confirm(key,g_iv[i]);
        if(r){ g_reserve_out=r; return i+1; }
    }
    return 0;
}

static inline int prefilter(const unsigned char *p){
    int z=0,h=0; for(int i=0;i<KEY_SZ;i++){if(p[i]==0)z++; if(p[i]>=0x80)h++;}
    return z<=10 && h>=3;   /* very loose: only skip ascii/zero-ish runs */
}

int main(void){
    pid_t pid=0;
    { FILE *p=popen("pgrep -x WeChat | head -1","r"); if(p){ if(fscanf(p,"%d",&pid)!=1)pid=0; pclose(p);} }
    if(pid<=0){fprintf(stderr,"WeChat not running\n");return 1;}
    printf("WeChat PID: %d\n",pid);
    task_t task;
    if(task_for_pid(mach_task_self(),pid,&task)!=KERN_SUCCESS){fprintf(stderr,"task_for_pid failed\n");return 1;}

    const char *home=getenv("HOME"),*su=getenv("SUDO_USER");
    if(su){struct passwd *pw=getpwnam(su); if(pw)home=pw->pw_dir;}
    if(!home)home="/root";
    char base[1024];
    snprintf(base,sizeof base,"%s/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files",home);
    const char *acct=getenv("WECHAT_ACCT");
    DIR *dr=opendir(base);
    if(dr){struct dirent *e; while((e=readdir(dr))){ if(e->d_name[0]=='.')continue;
        if(acct&&*acct&&!strstr(e->d_name,acct))continue;
        char sp[1200]; snprintf(sp,sizeof sp,"%s/%s/db_storage",base,e->d_name);
        struct stat st; if(stat(sp,&st)==0&&S_ISDIR(st.st_mode)){
            snprintf(g_db_base,sizeof g_db_base,"%s/%s",base,e->d_name);
            nftw(sp,nftw_collect,20,FTW_PHYS);} } closedir(dr);}
    printf("Collected %d encrypted DBs\n",g_db_count);
    if(!g_db_count){fprintf(stderr,"no DBs\n");return 1;}
    int target=0;
    for(int i=0;i<g_db_count;i++) if(strstr(g_db_rel[i],"message_0.db")&&!strstr(g_db_rel[i],"biz")){target=i;break;}
    const unsigned char *p1=g_db_page1[target];
    g_p1 = p1;
    /* IV candidates: reserve 80/64/48 -> IV at [4096-r : +16]; plus zero and salt */
    int rs[3]={80,64,48};
    for(int i=0;i<3;i++){ memcpy(g_iv[g_nIV], p1+(PAGE_SZ-rs[i]), 16); g_ivres[g_nIV]=rs[i]; g_nIV++; }
    memset(g_iv[g_nIV],0,16); g_ivres[g_nIV]=0; g_nIV++;
    memcpy(g_iv[g_nIV], p1, 16); g_ivres[g_nIV]=0; g_nIV++;   /* salt as IV */
    printf("Target: %s  salt=",g_db_rel[target]);
    for(int i=0;i<SALT_SZ;i++)printf("%02x",p1[i]); printf("  (%d IV variants)\n",g_nIV);

    int allmem=1; { const char *e=getenv("WECHAT_ALLMEM"); if(e&&(*e=='0'||!*e))allmem=0; }  /* default ALL readable */
    int usefilter=1; { const char *e=getenv("NOFILTER"); if(e&&*e&&*e!='0')usefilter=0; }

    unsigned char found[KEY_SZ]; int got=0, ivhit=0;
    size_t scanned=0, tested=0;
    mach_vm_address_t addr=0;
    while(!got){
        mach_vm_size_t size=0; vm_region_basic_info_data_64_t info;
        mach_msg_type_number_t ic=VM_REGION_BASIC_INFO_COUNT_64; mach_port_t obj;
        if(mach_vm_region(task,&addr,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&ic,&obj)!=KERN_SUCCESS)break;
        if(size==0){addr++;continue;}
        int want=allmem?(info.protection&VM_PROT_READ)
                       :((info.protection&(VM_PROT_READ|VM_PROT_WRITE))==(VM_PROT_READ|VM_PROT_WRITE));
        if(want){
            mach_vm_address_t ca=addr;
            while(ca<addr+size&&!got){
                mach_vm_size_t cs=addr+size-ca; if(cs>CHUNK_SIZE)cs=CHUNK_SIZE;
                vm_offset_t data; mach_msg_type_number_t dc;
                if(mach_vm_read(task,ca,cs,&data,&dc)==KERN_SUCCESS){
                    unsigned char *buf=(unsigned char*)data; size_t prev=scanned; scanned+=dc;
                    if(scanned/(128*1024*1024)!=prev/(128*1024*1024)){printf("  ...scanned %zuMB, tested %zu\n",scanned/1024/1024,tested);fflush(stdout);}
                    for(size_t i=0;i+KEY_SZ<=dc&&!got;i+=8){
                        if(usefilter&&!prefilter(buf+i))continue;
                        tested++;
                        int iv=check_key(buf+i);
                        if(iv){memcpy(found,buf+i,KEY_SZ);ivhit=iv;got=1;break;}
                    }
                    mach_vm_deallocate(mach_task_self(),data,dc);
                }
                if(cs>64)ca+=cs-64; else ca+=cs;
            }
        }
        addr+=size;
    }
    printf("Scanned %zuMB, tested %zu\n",scanned/1024/1024,tested);
    if(!got){fprintf(stderr,"KEY NOT FOUND\n");return 2;}
    char kh[65]; for(int i=0;i<KEY_SZ;i++)sprintf(kh+2*i,"%02x",found[i]);
    const char *ivdesc[8]={"reserve80","reserve64","reserve48","zeroIV","saltIV"};
    printf("FOUND KEY: %s  (IV=%s)\n", kh, ivhit>=1&&ivhit<=5?ivdesc[ivhit-1]:"?");
    printf(">>> 记下这个 key 和 IV 模式，贴给 Claude\n");
    return 0;
}
